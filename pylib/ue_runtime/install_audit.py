"""
Read-only drift audit for an installed task runtime.

The installer can copy the shared runtime into another project; this audit
proves whether that installed copy still matches the current package manifest.
"""

import hashlib
import json
from pathlib import Path

from ue_runtime.installer import INSTALL_RECEIPT_PATH, INSTALL_RECEIPT_SCHEMA_VERSION
from ue_runtime.package import build_package_manifest


INSTALL_AUDIT_SCHEMA_VERSION = "ue-task-runtime-install-audit/v1"

# Submodule-linked consumption layout (primary channel; see shared README
# "Runtime distribution channels"). Vendored copies use package runtime_path.
LINKED_RUNTIME_PATH = "agent-stack-shared/pylib/ue_runtime"


def _detect_consumption_mode(target_root, package):
    vendored_path = package.get("runtime_path", "Content/Python/ue_runtime")
    if (target_root / vendored_path).is_dir():
        return "vendored", vendored_path
    if (target_root / LINKED_RUNTIME_PATH).is_dir():
        return "linked", LINKED_RUNTIME_PATH
    return "vendored", vendored_path


def audit_runtime_install(target_root, package_manifest=None):
    target_root = Path(target_root).resolve()
    package = package_manifest or build_package_manifest()
    mode, runtime_path = _detect_consumption_mode(target_root, package)
    expected = {
        record["path"]: record
        for record in package.get("files", [])
    }
    issues = []
    checked = 0

    def _target_for(rel_path):
        if mode == "linked":
            return target_root / LINKED_RUNTIME_PATH / Path(rel_path).name
        return target_root / rel_path

    for rel_path, record in sorted(expected.items()):
        checked += 1
        target = _target_for(rel_path)
        if not target.exists():
            issues.append(_issue("missing_file", "missing runtime file: %s" % rel_path, rel_path))
            continue
        if not target.is_file():
            issues.append(_issue("not_a_file", "runtime path is not a file: %s" % rel_path, rel_path))
            continue
        try:
            data = target.read_bytes()
        except OSError as exc:
            issues.append(_issue("unreadable_file", "cannot read runtime file %s: %s" % (rel_path, exc), rel_path))
            continue
        if len(data) != record.get("bytes"):
            issues.append(_issue("bytes_mismatch", "byte size mismatch: %s" % rel_path, rel_path))
        expected_sha = record.get("sha256")
        actual_sha = hashlib.sha256(data).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            issues.append(_issue("sha256_mismatch", "sha256 mismatch: %s" % rel_path, rel_path))

    runtime_root = target_root / runtime_path
    if not runtime_root.exists():
        issues.append(_issue("runtime_dir_missing", "runtime directory missing: %s" % runtime_path, runtime_path))
    elif runtime_root.is_dir():
        expected_names = {Path(rel).name for rel in expected}
        for path in sorted(runtime_root.glob("*.py")):
            rel_path = _relative_project_path(target_root, path)
            known = rel_path in expected if mode == "vendored" else path.name in expected_names
            if not known:
                issues.append(_issue("extra_runtime_file", "extra runtime file: %s" % rel_path, rel_path))
    else:
        issues.append(_issue("runtime_dir_not_directory", "runtime path is not a directory: %s" % runtime_path, runtime_path))

    summary = {
        "expected_files": len(expected),
        "checked_files": checked,
        "missing_files": len([issue for issue in issues if issue["code"] == "missing_file"]),
        "changed_files": len([
            issue for issue in issues
            if issue["code"] in ("bytes_mismatch", "sha256_mismatch", "unreadable_file", "not_a_file")
        ]),
        "extra_files": len([issue for issue in issues if issue["code"] == "extra_runtime_file"]),
    }
    receipt = _read_receipt(target_root, package, issues)
    receipt_data = receipt.pop("_data", None)
    receipt_checked = _audit_receipt_runtime_files(target_root, receipt_data, issues)
    receipt_changed = len([
        issue for issue in issues
        if issue["code"] in (
            "receipt_missing_file",
            "receipt_baseline_not_a_file",
            "receipt_unreadable_file",
            "receipt_bytes_mismatch",
            "receipt_sha256_mismatch",
        )
    ])
    summary["receipt_checked_files"] = receipt_checked
    summary["receipt_changed_files"] = receipt_changed
    return {
        "schema_version": INSTALL_AUDIT_SCHEMA_VERSION,
        "ok": not issues,
        "mode": mode,
        "runtime_root": runtime_path,
        "target_root": str(target_root),
        "package": {
            "schema_version": package.get("schema_version"),
            "package": package.get("package"),
            "runtime_version": package.get("runtime_version"),
            "runtime_api": package.get("runtime_api"),
            "runtime_path": package.get("runtime_path"),
            "file_count": package.get("file_count"),
        },
        "receipt": receipt,
        "summary": summary,
        "issue_count": len(issues),
        "issues": issues,
    }


def _relative_project_path(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_receipt(target_root, package, issues):
    receipt_path = target_root / INSTALL_RECEIPT_PATH
    result = {
        "path": INSTALL_RECEIPT_PATH,
        "present": False,
        "ok": True,
        "schema_version": None,
        "source": None,
        "runtime_version": None,
        "runtime_api": None,
        "file_count": None,
        "registry_factory": None,
        "bootstrap_scripts": [],
        "_data": None,
    }
    if not receipt_path.exists():
        return result
    result["present"] = True
    if not receipt_path.is_file():
        result["ok"] = False
        issues.append(_issue("receipt_not_a_file", "install receipt path is not a file", INSTALL_RECEIPT_PATH))
        return result
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        result["ok"] = False
        issues.append(_issue("receipt_read_error", "cannot read install receipt: %s" % exc, INSTALL_RECEIPT_PATH))
        return result

    receipt_package = receipt.get("package") or {}
    result.update({
        "schema_version": receipt.get("schema_version"),
        "source": receipt.get("source"),
        "runtime_version": receipt_package.get("runtime_version"),
        "runtime_api": receipt_package.get("runtime_api"),
        "file_count": receipt_package.get("file_count"),
        "registry_factory": receipt.get("registry_factory"),
        "bootstrap_scripts": list(receipt.get("bootstrap_scripts") or []),
        "_data": receipt,
    })
    if receipt.get("schema_version") != INSTALL_RECEIPT_SCHEMA_VERSION:
        result["ok"] = False
        issues.append(_issue("unsupported_receipt_schema", "unsupported install receipt schema", INSTALL_RECEIPT_PATH))
    if receipt_package.get("runtime_api") != package.get("runtime_api"):
        result["ok"] = False
        issues.append(_issue("receipt_runtime_api_mismatch", "install receipt runtime_api does not match package", INSTALL_RECEIPT_PATH))
    if receipt_package.get("runtime_version") != package.get("runtime_version"):
        result["ok"] = False
        issues.append(_issue("receipt_runtime_version_mismatch", "install receipt runtime_version does not match package", INSTALL_RECEIPT_PATH))
    if receipt_package.get("file_count") != package.get("file_count"):
        result["ok"] = False
        issues.append(_issue("receipt_file_count_mismatch", "install receipt file_count does not match package", INSTALL_RECEIPT_PATH))
    return result


def _audit_receipt_runtime_files(target_root, receipt, issues):
    if not receipt:
        return 0
    checked = 0
    seen = set()
    for record in receipt.get("runtime_files") or []:
        rel_path = record.get("path")
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)
        checked += 1
        target = target_root / rel_path
        if not target.exists():
            issues.append(_issue("receipt_missing_file", "receipt baseline file missing: %s" % rel_path, rel_path))
            continue
        if not target.is_file():
            issues.append(_issue("receipt_baseline_not_a_file", "receipt baseline path is not a file: %s" % rel_path, rel_path))
            continue
        try:
            data = target.read_bytes()
        except OSError as exc:
            issues.append(_issue("receipt_unreadable_file", "cannot read receipt baseline file %s: %s" % (rel_path, exc), rel_path))
            continue
        if record.get("bytes") is not None and len(data) != record.get("bytes"):
            issues.append(_issue("receipt_bytes_mismatch", "receipt byte size mismatch: %s" % rel_path, rel_path))
        expected_sha = record.get("sha256")
        actual_sha = hashlib.sha256(data).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            issues.append(_issue("receipt_sha256_mismatch", "receipt sha256 mismatch: %s" % rel_path, rel_path))
    return checked


def _issue(code, message, path):
    return {
        "code": code,
        "message": message,
        "path": path,
    }
