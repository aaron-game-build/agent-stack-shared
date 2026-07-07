"""Unit tests for pylib/kb_lifecycle (UE-light package, no unreal dependency)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

PYLIB_ROOT = Path(__file__).resolve().parents[2]
if str(PYLIB_ROOT) not in sys.path:
    sys.path.insert(0, str(PYLIB_ROOT))

from kb_lifecycle import checks  # noqa: E402
from kb_lifecycle.cli import main as cli_main  # noqa: E402
from kb_lifecycle.frontmatter import parse_frontmatter  # noqa: E402


# ---------------------------------------------------------------------------
# frontmatter.parse_frontmatter
# ---------------------------------------------------------------------------


class FrontmatterParseTests(unittest.TestCase):
    def test_parses_scalars_and_list(self):
        text = (
            "---\n"
            "kb_type: module\n"
            "domain: process\n"
            "status: active\n"
            "updated: 2026-07-07\n"
            "tags:\n"
            "  - concept:Example\n"
            "  - pitfall:ExampleThing\n"
            "related_concepts:\n"
            "  - ../knowledge-base-entry.md\n"
            "---\n"
            "\n"
            "# Body\n"
        )
        data = parse_frontmatter(text)
        self.assertIsNotNone(data)
        self.assertEqual(data["kb_type"], "module")
        self.assertEqual(data["domain"], "process")
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["updated"], "2026-07-07")
        self.assertEqual(data["tags"], ["concept:Example", "pitfall:ExampleThing"])
        self.assertEqual(data["related_concepts"], ["../knowledge-base-entry.md"])

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(parse_frontmatter("# Just a heading\n\nSome text.\n"))

    def test_unclosed_frontmatter_returns_none(self):
        text = "---\nkb_type: module\nstatus: active\n"
        self.assertIsNone(parse_frontmatter(text))

    def test_malformed_line_returns_none(self):
        text = "---\nkb_type module\n---\n"
        self.assertIsNone(parse_frontmatter(text))

    def test_ignores_comments_and_blank_lines(self):
        text = (
            "---\n"
            "# a comment\n"
            "\n"
            "kb_type: concept\n"
            "\n"
            "---\n"
        )
        data = parse_frontmatter(text)
        self.assertEqual(data["kb_type"], "concept")

    def test_quoted_scalar_is_unquoted(self):
        text = '---\nkb_type: concept\ntitle: "Hello World"\n---\n'
        data = parse_frontmatter(text)
        self.assertEqual(data["title"], "Hello World")

    def test_empty_list_value_parses_to_empty_list(self):
        text = "---\nkb_type: concept\ntags:\n---\n"
        data = parse_frontmatter(text)
        self.assertEqual(data["tags"], [])


# ---------------------------------------------------------------------------
# Fixture KB builder
# ---------------------------------------------------------------------------


def _write(root: Path, rel_path: str, content: str):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _entry(kb_type="module", status="active", updated="2026-07-01", tags=None, related=None, extra=""):
    lines = ["---", "kb_type: %s" % kb_type]
    if status is not None:
        lines.append("status: %s" % status)
    if updated is not None:
        lines.append("updated: %s" % updated)
    if tags is not None:
        lines.append("tags:")
        for tag in tags:
            lines.append("  - %s" % tag)
    if related is not None:
        lines.append("related_concepts:")
        for item in related:
            lines.append("  - %s" % item)
    lines.append("---")
    lines.append("")
    lines.append("# Entry")
    lines.append("")
    if extra:
        lines.append(extra)
    return "\n".join(lines) + "\n"


class KbLifecycleChecksTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.kb_root = Path(self._tmp.name)

    # -- metadata --------------------------------------------------------

    def test_metadata_missing_fields_warn_by_default(self):
        _write(self.kb_root, "modules/no-status.md", _entry(status=None, updated=None))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter)
        metadata_issues = [i for i in issues if i.check == "metadata"]
        self.assertEqual(len(metadata_issues), 2)
        for issue in metadata_issues:
            self.assertEqual(issue.severity, "warning")

    def test_metadata_missing_fields_error_in_strict_mode(self):
        _write(self.kb_root, "modules/no-status.md", _entry(status=None, updated=None))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, strict=True)
        metadata_issues = [i for i in issues if i.check == "metadata"]
        self.assertEqual(len(metadata_issues), 2)
        for issue in metadata_issues:
            self.assertEqual(issue.severity, "error")

    def test_metadata_invalid_status_is_always_error(self):
        _write(self.kb_root, "modules/bad-status.md", _entry(status="wip", updated="2026-07-01"))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter)
        matching = [i for i in issues if i.check == "metadata" and "invalid status" in i.message]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].severity, "error")

    def test_metadata_invalid_date_is_always_error(self):
        _write(self.kb_root, "modules/bad-date.md", _entry(status="active", updated="07/01/2026"))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter)
        matching = [i for i in issues if i.check == "metadata" and "invalid updated date" in i.message]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].severity, "error")

    def test_metadata_clean_entry_has_no_issues(self):
        _write(self.kb_root, "modules/clean.md", _entry(status="active", updated="2026-07-01"))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual([i for i in issues if i.check == "metadata"], [])

    # -- stale -------------------------------------------------------------

    def test_stale_flags_old_active_entry(self):
        _write(self.kb_root, "modules/old.md", _entry(status="active", updated="2025-01-01"))
        entries, issues = checks.run_all_checks(
            self.kb_root, parse_frontmatter, stale_days=180, today=date(2026, 7, 7)
        )
        stale_issues = [i for i in issues if i.check == "stale"]
        self.assertEqual(len(stale_issues), 1)
        self.assertIn("modules/old.md", stale_issues[0].path)

    def test_stale_does_not_flag_recent_active_entry(self):
        _write(self.kb_root, "modules/recent.md", _entry(status="active", updated="2026-06-01"))
        entries, issues = checks.run_all_checks(
            self.kb_root, parse_frontmatter, stale_days=180, today=date(2026, 7, 7)
        )
        self.assertEqual([i for i in issues if i.check == "stale"], [])

    def test_stale_ignores_deprecated_entries(self):
        _write(self.kb_root, "modules/old-deprecated.md", _entry(status="deprecated", updated="2020-01-01"))
        entries, issues = checks.run_all_checks(
            self.kb_root, parse_frontmatter, stale_days=180, today=date(2026, 7, 7)
        )
        self.assertEqual([i for i in issues if i.check == "stale"], [])

    def test_stale_today_injection_is_deterministic(self):
        _write(self.kb_root, "modules/edge.md", _entry(status="active", updated="2026-01-01"))
        # Exactly 180 days later: not stale (uses > not >=).
        entries, issues = checks.run_all_checks(
            self.kb_root, parse_frontmatter, stale_days=180, today=date(2026, 6, 30)
        )
        self.assertEqual([i for i in issues if i.check == "stale"], [])
        # One day further: stale.
        entries, issues = checks.run_all_checks(
            self.kb_root, parse_frontmatter, stale_days=180, today=date(2026, 7, 1)
        )
        self.assertEqual(len([i for i in issues if i.check == "stale"]), 1)

    # -- deprecated_ref ------------------------------------------------------

    def test_deprecated_ref_flags_reference_from_active_entry(self):
        _write(self.kb_root, "modules/old.md", _entry(status="deprecated", updated="2025-01-01"))
        _write(
            self.kb_root,
            "modules/new.md",
            _entry(status="active", updated="2026-07-01", related=["old.md"]),
        )
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        dep_issues = [i for i in issues if i.check == "deprecated_ref"]
        self.assertEqual(len(dep_issues), 1)
        self.assertEqual(dep_issues[0].path, "modules/old.md")
        self.assertIn("modules/new.md", dep_issues[0].message)

    def test_deprecated_ref_flags_reference_from_top_level_index(self):
        _write(self.kb_root, "modules/old.md", _entry(status="deprecated", updated="2025-01-01"))
        _write(self.kb_root, "index.md", "# Index\n\nSee [old](modules/old.md).\n")
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        dep_issues = [i for i in issues if i.check == "deprecated_ref"]
        self.assertEqual(len(dep_issues), 1)

    def test_deprecated_ref_no_issue_when_unreferenced(self):
        _write(self.kb_root, "modules/old.md", _entry(status="deprecated", updated="2025-01-01"))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual([i for i in issues if i.check == "deprecated_ref"], [])

    # -- merge_candidate -----------------------------------------------------

    def test_merge_candidate_flags_high_tag_overlap(self):
        _write(
            self.kb_root,
            "modules/a.md",
            _entry(status="active", updated="2026-07-01", tags=["concept:X", "concept:Y"]),
        )
        _write(
            self.kb_root,
            "modules/b.md",
            _entry(status="active", updated="2026-07-01", tags=["concept:X", "concept:Y"]),
        )
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        merge_issues = [i for i in issues if i.check == "merge_candidate"]
        self.assertEqual(len(merge_issues), 1)

    def test_merge_candidate_no_flag_for_low_tag_overlap(self):
        _write(
            self.kb_root,
            "modules/a.md",
            _entry(status="active", updated="2026-07-01", tags=["concept:X"]),
        )
        _write(
            self.kb_root,
            "modules/b.md",
            _entry(status="active", updated="2026-07-01", tags=["concept:Z"]),
        )
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual([i for i in issues if i.check == "merge_candidate"], [])

    def test_merge_candidate_flags_same_filename_in_different_subdirs(self):
        _write(self.kb_root, "modules/dup.md", _entry(status="active", updated="2026-07-01", tags=["concept:A"]))
        _write(self.kb_root, "concepts/dup.md", _entry(status="active", updated="2026-07-01", tags=["concept:B"]))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        merge_issues = [i for i in issues if i.check == "merge_candidate"]
        self.assertEqual(len(merge_issues), 1)
        self.assertIn("same filename", merge_issues[0].message)

    def test_merge_candidate_threshold_is_parameterized(self):
        _write(
            self.kb_root,
            "modules/a.md",
            _entry(status="active", updated="2026-07-01", tags=["concept:X", "concept:Y", "concept:Z"]),
        )
        _write(
            self.kb_root,
            "modules/b.md",
            _entry(status="active", updated="2026-07-01", tags=["concept:X"]),
        )
        # Jaccard = 1/3 ~= 0.33: not flagged at default 0.5 threshold.
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual([i for i in issues if i.check == "merge_candidate"], [])
        # Flagged when threshold is lowered.
        entries, issues = checks.run_all_checks(
            self.kb_root, parse_frontmatter, today=date(2026, 7, 7), jaccard_threshold=0.3
        )
        self.assertEqual(len([i for i in issues if i.check == "merge_candidate"]), 1)

    # -- orphan --------------------------------------------------------------

    def test_orphan_flags_unreferenced_entry(self):
        _write(self.kb_root, "modules/lonely.md", _entry(status="active", updated="2026-07-01"))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        orphan_issues = [i for i in issues if i.check == "orphan"]
        self.assertEqual(len(orphan_issues), 1)
        self.assertEqual(orphan_issues[0].path, "modules/lonely.md")

    def test_orphan_not_flagged_when_referenced_by_index(self):
        _write(self.kb_root, "modules/known.md", _entry(status="active", updated="2026-07-01"))
        _write(self.kb_root, "index.md", "# Index\n\nSee [known](modules/known.md).\n")
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual(
            [i for i in issues if i.check == "orphan" and i.path == "modules/known.md"], []
        )

    def test_orphan_not_flagged_when_referenced_by_related_concepts(self):
        _write(self.kb_root, "modules/base.md", _entry(status="active", updated="2026-07-01"))
        _write(
            self.kb_root,
            "modules/derived.md",
            _entry(status="active", updated="2026-07-01", related=["base.md"]),
        )
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual(
            [i for i in issues if i.check == "orphan" and i.path == "modules/base.md"], []
        )

    # -- non-entry documents --------------------------------------------------

    def test_files_without_kb_type_are_not_entries(self):
        _write(self.kb_root, "modules/plain.md", "# Plain doc\n\nNo frontmatter at all.\n")
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual(entries, [])
        self.assertEqual(issues, [])

    def test_non_concept_module_kb_type_is_not_an_entry(self):
        _write(self.kb_root, "modules/other.md", _entry(kb_type="index", status="active", updated="2026-07-01"))
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        self.assertEqual(entries, [])

    def test_broken_frontmatter_reported_as_metadata_error(self):
        _write(self.kb_root, "modules/broken.md", "---\nkb_type module\n---\n")
        entries, issues = checks.run_all_checks(self.kb_root, parse_frontmatter, today=date(2026, 7, 7))
        broken_issues = [i for i in issues if i.path == "modules/broken.md"]
        self.assertEqual(len(broken_issues), 1)
        self.assertEqual(broken_issues[0].severity, "error")


# ---------------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------------


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.kb_root = Path(self._tmp.name)

    def _run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = cli_main(argv)
        return exit_code, out.getvalue()

    def test_clean_kb_prints_ok_token_and_exits_zero(self):
        _write(self.kb_root, "modules/clean.md", _entry(status="active", updated="2026-07-01"))
        _write(self.kb_root, "index.md", "# Index\n\nSee [clean](modules/clean.md).\n")
        exit_code, output = self._run_cli(
            ["--kb-root", str(self.kb_root), "--today", "2026-07-07"]
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("KB_LIFECYCLE_OK entries=1", output)

    def test_kb_with_warnings_exits_zero_and_prints_issues_token(self):
        _write(self.kb_root, "modules/lonely.md", _entry(status="active", updated="2020-01-01"))
        exit_code, output = self._run_cli(
            ["--kb-root", str(self.kb_root), "--today", "2026-07-07"]
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("KB_LIFECYCLE_ISSUES entries=1", output)
        self.assertIn("errors=0", output)
        self.assertIn("warnings=", output)

    def test_kb_with_errors_exits_one(self):
        _write(self.kb_root, "modules/bad.md", _entry(status="active", updated="not-a-date"))
        exit_code, output = self._run_cli(
            ["--kb-root", str(self.kb_root), "--today", "2026-07-07"]
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("errors=1", output)

    def test_strict_flag_promotes_missing_fields_to_errors(self):
        _write(self.kb_root, "modules/incomplete.md", _entry(status=None, updated=None))
        exit_code, output = self._run_cli(
            ["--kb-root", str(self.kb_root), "--today", "2026-07-07", "--strict"]
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("errors=2", output)

    def test_json_output_is_valid_and_structured(self):
        _write(self.kb_root, "modules/clean.md", _entry(status="active", updated="2026-07-01"))
        _write(self.kb_root, "index.md", "# Index\n\nSee [clean](modules/clean.md).\n")
        exit_code, output = self._run_cli(
            ["--kb-root", str(self.kb_root), "--today", "2026-07-07", "--json"]
        )
        self.assertEqual(exit_code, 0)
        report = json.loads(output)
        self.assertEqual(report["entry_count"], 1)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["issues"], [])

    def test_missing_kb_root_errors(self):
        exit_code, _ = self._run_cli(["--kb-root", str(self.kb_root / "does-not-exist")])
        self.assertEqual(exit_code, 1)

    def test_output_is_ascii_and_uses_hyphen_separators(self):
        _write(self.kb_root, "modules/lonely.md", _entry(status="active", updated="2020-01-01"))
        _, output = self._run_cli(["--kb-root", str(self.kb_root), "--today", "2026-07-07"])
        output.encode("ascii")  # raises UnicodeEncodeError if non-ASCII slipped in
        self.assertNotIn("—", output)  # no em-dash
        self.assertIn("--", output)


# ---------------------------------------------------------------------------
# Boundary self-scan (mirrors ue_probe.tests.test_ue_probe.BoundaryTests)
# ---------------------------------------------------------------------------


class BoundaryTests(unittest.TestCase):
    def _forbidden_markers(self):
        # Built via string concatenation so this list itself never contains a
        # literal forbidden token (which would trip the very scan it feeds,
        # or a repo-wide marker scan run over the test sources).
        drive = "G" + ":" + "/" + "UEProjects"
        drive_back = "G" + ":" + "\\" + "UEProjects"
        game_root = "/" + "Game" + "/"
        oath = "Oath" + "board"
        roguelike = "MyRogue" + "likeGame"
        return (oath, roguelike, drive, drive_back, game_root)

    def test_no_project_markers_in_package_sources(self):
        pkg_dir = PYLIB_ROOT / "kb_lifecycle"
        forbidden = self._forbidden_markers()
        offenders = []
        for py in pkg_dir.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in text:
                    offenders.append("%s: %s" % (py.relative_to(PYLIB_ROOT), marker))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
