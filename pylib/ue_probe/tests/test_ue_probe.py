"""Unit tests for pylib/ue_probe (editor-only package, tested via a stub unreal).

A fake ``unreal`` module is injected into sys.modules before importing
``ue_probe.base``, so these tests run in plain Python (shared CI + consumer
static gates) without a UE Editor.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


PYLIB_ROOT = Path(__file__).resolve().parents[2]
if str(PYLIB_ROOT) not in sys.path:
    sys.path.insert(0, str(PYLIB_ROOT))


def _make_unreal_stub():
    stub = types.ModuleType("unreal")

    class Paths:
        _content_dir = ""
        _saved_dir = ""

        @staticmethod
        def project_content_dir():
            return Paths._content_dir

        @staticmethod
        def project_saved_dir():
            return Paths._saved_dir

    class GameplayStatics:
        @staticmethod
        def get_game_instance(world):
            return getattr(world, "game_instance", None)

        @staticmethod
        def get_all_actors_of_class(world, cls):
            return list(getattr(world, "actors", ()))

    stub.Paths = Paths
    stub.GameplayStatics = GameplayStatics
    stub.load_class = lambda outer, path: None
    return stub


_UNREAL_STUB = _make_unreal_stub()
sys.modules.setdefault("unreal", _UNREAL_STUB)

from ue_probe import base  # noqa: E402


class FailTokenTests(unittest.TestCase):
    def test_fail_with_token_prints_ascii_separator_and_exits_1(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                base.fail_with_token("PROBE_X", "boom")
        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(out.getvalue().strip(), "PROBE_X_FAILED - boom")

    def test_fail_probe_and_fail_audit_delegate(self):
        for fn in (base.fail_probe, base.fail_audit):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                with self.assertRaises(SystemExit):
                    fn("T", "m")
            self.assertIn("T_FAILED - m", out.getvalue())


class WriteResultTests(unittest.TestCase):
    def test_write_result_creates_json_under_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            _UNREAL_STUB.Paths._saved_dir = tmp
            path = base.write_result(
                "ProjX", "result.json", "ok", token="PROBE_X_OK", extra=7
            )
            self.assertEqual(
                Path(path), Path(tmp) / "Automation" / "ProjX" / "result.json"
            )
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["token"], "PROBE_X_OK")
            self.assertEqual(data["extra"], 7)
            self.assertIn("generated_at_epoch", data)


class RunProbeModuleTests(unittest.TestCase):
    def test_runs_main_registers_module_and_returns_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            _UNREAL_STUB.Paths._content_dir = tmp
            probes = Path(tmp) / "Python" / "probes"
            probes.mkdir(parents=True)
            (probes / "probe_stub_ok.py").write_text(
                "def main():\n    return 'ran'\n", encoding="utf-8"
            )
            self.assertEqual(base.run_probe_module("probe_stub_ok.py"), "ran")
            self.assertIn("probe_stub_ok", sys.modules)

    def test_missing_file_fails_with_token_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            _UNREAL_STUB.Paths._content_dir = tmp
            (Path(tmp) / "Python").mkdir(parents=True)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                with self.assertRaises(SystemExit):
                    base.run_probe_module("nope.py", token_prefix="PROBE_P")
            self.assertIn("PROBE_P_FAILED - missing probe file:", out.getvalue())


class ClassHelpersTests(unittest.TestCase):
    def test_class_name_falls_back_to_type_on_error(self):
        class Broken:
            def get_class(self):
                raise RuntimeError("no rtti")

        self.assertIn("Broken", base.class_name(Broken()))

    def test_class_name_empty_for_none(self):
        self.assertEqual(base.class_name(None), "")

    def test_load_class_fails_when_unresolved(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                base.load_class("/Script/Missing.Thing", "PROBE_C")
        self.assertIn("missing class: /Script/Missing.Thing", out.getvalue())


class SubsystemTests(unittest.TestCase):
    def test_none_world_returns_none(self):
        self.assertIsNone(base.get_game_instance_subsystem(None, "/Script/X.Y"))

    def test_get_subsystem_path(self):
        marker = object()

        class GameInstance:
            def get_subsystem(self, cls):
                return marker

        world = types.SimpleNamespace(game_instance=GameInstance())
        old_load = _UNREAL_STUB.load_class
        _UNREAL_STUB.load_class = lambda outer, path: type("FakeCls", (), {})
        try:
            self.assertIs(
                base.get_game_instance_subsystem(world, "/Script/X.Y"), marker
            )
        finally:
            _UNREAL_STUB.load_class = old_load


class BoundaryTests(unittest.TestCase):
    # Drive-path markers are concatenated so this file itself passes the
    # repo-wide scan in scripts/forbidden_marker_check.py.
    FORBIDDEN = (
        "Oathboard",
        "MyRoguelikeGame",
        "G:/" + "UEProjects",
        "G:\\" + "UEProjects",
        "/Game/",
    )

    def test_no_project_markers_in_package_sources(self):
        pkg_dir = PYLIB_ROOT / "ue_probe"
        offenders = []
        for py in pkg_dir.glob("*.py"):
            text = py.read_text(encoding="utf-8")
            for marker in self.FORBIDDEN:
                if marker in text:
                    offenders.append(f"{py.name}: {marker}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
