"""Unit tests for agent-stack/pylib/sdd_tdd (no UE dependency)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PYLIB_ROOT = Path(__file__).resolve().parents[2]
if str(PYLIB_ROOT) not in sys.path:
    sys.path.insert(0, str(PYLIB_ROOT))

from sdd_tdd.audit_runner import run_audit_modules  # noqa: E402
from sdd_tdd.contract_model import (  # noqa: E402
    can_promote,
    clear_contracts,
    register_contract,
    validate_contract_shape,
)
from sdd_tdd.evidence_pack import atomic_write_text, create_evidence_pack  # noqa: E402
from sdd_tdd.probe_hygiene import check_probes  # noqa: E402
from sdd_tdd.spec_schema import validate_catalog  # noqa: E402


class SpecSchemaTests(unittest.TestCase):
    def test_valid_catalog_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "Docs" / "spec.md"
            doc.parent.mkdir(parents=True)
            doc.write_text("# spec", encoding="utf-8")
            catalog = {
                "demo.feature": {
                    "status": "active",
                    "domain_model": ["DemoType"],
                    "contract_refs": ["Docs/spec.md"],
                    "solution_refs": ["Docs/spec.md"],
                    "validation": ["python validate.py prints DEMO_OK"],
                }
            }
            issues = validate_catalog(catalog, root)
            self.assertEqual(issues, [])

    def test_missing_ref_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = {
                "demo.feature": {
                    "status": "active",
                    "domain_model": ["DemoType"],
                    "contract_refs": ["Docs/missing.md"],
                    "solution_refs": ["Docs/missing.md"],
                    "validation": ["check"],
                }
            }
            issues = validate_catalog(catalog, Path(tmp))
            codes = {issue.code for issue in issues}
            self.assertIn("missing_ref", codes)


class ProbeHygieneTests(unittest.TestCase):
    def test_good_probe_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe_dir = Path(tmp)
            (probe_dir / "probe_demo.py").write_text(
                "OK = 'PROBE_DEMO_OK'\n"
                "def main():\n"
                "    print(OK)\n"
                "if __name__ == '__main__':\n"
                "    main()\n",
                encoding="utf-8",
            )
            issues = check_probes(probe_dir, registered_stems={"probe_demo"})
            self.assertEqual(issues, [])

    def test_bad_name_fails_r1(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe_dir = Path(tmp)
            (probe_dir / "bad_demo.py").write_text("def main(): pass\n", encoding="utf-8")
            issues = check_probes(probe_dir)
            self.assertTrue(any(issue.rule == "R1" for issue in issues))


class ContractModelTests(unittest.TestCase):
    def setUp(self):
        clear_contracts()

    def test_register_and_validate(self):
        contract = {
            "contract_id": "demo.input",
            "claims": [{"claim_id": "press_q", "guarantees": ["ability fires"]}],
        }
        register_contract(contract)
        self.assertEqual(validate_contract_shape(contract), [])

    def test_evidence_promotion_order(self):
        self.assertTrue(can_promote("ForcedResult", "NaturalPlay"))
        self.assertFalse(can_promote("NaturalPlay", "ForcedResult"))


class EvidencePackTests(unittest.TestCase):
    def test_create_unique_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default = root / "Saved" / "Evidence"
            pack = create_evidence_pack(root, default)
            self.assertTrue(pack.evidence_dir.is_dir())
            payload = pack.evidence_dir / "summary.json"
            atomic_write_text(payload, json.dumps({"ok": True}))
            self.assertTrue(payload.is_file())


class AuditRunnerTests(unittest.TestCase):
    def test_run_modules_reports_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            content_python = Path(tmp)
            audits = content_python / "audits"
            audits.mkdir()
            (audits / "__init__.py").write_text("", encoding="utf-8")
            (audits / "audit_pass.py").write_text(
                "def main():\n    print('AUDIT_PASS_OK')\n",
                encoding="utf-8",
            )
            (audits / "audit_fail.py").write_text(
                "def main():\n    raise SystemExit(1)\n",
                encoding="utf-8",
            )
            results, all_ok = run_audit_modules(
                ["audits.audit_pass", "audits.audit_fail"],
                content_python_dir=content_python,
            )
            self.assertFalse(all_ok)
            self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
