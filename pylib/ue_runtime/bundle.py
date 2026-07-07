"""
Deterministic zip bundle writer for the portable task runtime.

The bundle is the handoff artifact for projects that should consume the runtime
without reading files directly from the source repository. It contains the
shared ``ue_runtime`` package, optional project scaffold files, and a manifest
describing every archived entry.
"""

import hashlib
import json
import zipfile
from pathlib import Path

from ue_runtime.package import RUNTIME_API_VERSION, build_package_manifest
from ue_runtime.scaffold import build_project_scaffold


BUNDLE_SCHEMA_VERSION = "ue-task-runtime-bundle/v1"
BUNDLE_VERIFY_SCHEMA_VERSION = "ue-task-runtime-bundle-verify/v1"
BUNDLE_MANIFEST_PATH = "ue-runtime-bundle.json"
_ZIP_DATE_TIME = (2026, 1, 1, 0, 0, 0)


def build_bundle_manifest(
    project_name="ExampleProject",
    registry_module="project_tasks.registry",
    bootstrap_name="task.py",
    include_scaffold=True,
):
    package = build_package_manifest()
    scaffold = build_project_scaffold(
        project_name=project_name,
        registry_module=registry_module,
        bootstrap_name=bootstrap_name,
    )
    entries = []
    for record in package["files"]:
        entries.append({
            "path": record["path"],
            "kind": "runtime_file",
            "sha256": record["sha256"],
            "bytes": record["bytes"],
        })
    if include_scaffold:
        for path, content in sorted(scaffold["files"].items()):
            data = content.encode("utf-8")
            entries.append({
                "path": path,
                "kind": "scaffold_file",
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "archive_format": "zip",
        "manifest_path": BUNDLE_MANIFEST_PATH,
        "package": {
            "schema_version": package["schema_version"],
            "package": package["package"],
            "runtime_version": package["runtime_version"],
            "runtime_api": package["runtime_api"],
            "compatibility": dict(package["compatibility"]),
            "runtime_path": package["runtime_path"],
            "file_count": package["file_count"],
        },
        "scaffold": {
            "schema_version": scaffold["schema_version"],
            "included": bool(include_scaffold),
            "project_name": scaffold["project_name"],
            "registry_factory": scaffold["registry_factory"],
            "bootstrap_scripts": list(scaffold["bootstrap_scripts"]),
            "file_count": len(scaffold["files"]) if include_scaffold else 0,
            "files": sorted(scaffold["files"]) if include_scaffold else [],
        },
        "entry_count": len(entries) + 1,
        "output_path": None,
        "archive_bytes": None,
        "archive_sha256": None,
        "entries": [
            {
                "path": BUNDLE_MANIFEST_PATH,
                "kind": "bundle_manifest",
                "sha256": None,
                "bytes": None,
            },
            *entries,
        ],
        "verify_commands": list(scaffold["next_commands"]) if include_scaffold else [],
    }


def write_bundle(
    output_path,
    project_name="ExampleProject",
    registry_module="project_tasks.registry",
    bootstrap_name="task.py",
    include_scaffold=True,
):
    output = Path(output_path).resolve()
    manifest = build_bundle_manifest(
        project_name=project_name,
        registry_module=registry_module,
        bootstrap_name=bootstrap_name,
        include_scaffold=include_scaffold,
    )
    runtime_payloads = _runtime_file_payloads(manifest)
    scaffold_payloads = {}
    if include_scaffold:
        scaffold = build_project_scaffold(
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
        )
        scaffold_payloads = {
            path: content.encode("utf-8")
            for path, content in scaffold["files"].items()
        }
    payloads = {
        BUNDLE_MANIFEST_PATH: json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        **runtime_payloads,
        **scaffold_payloads,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(payloads):
            info = zipfile.ZipInfo(path.replace("\\", "/"), _ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payloads[path])
    data = output.read_bytes()
    result = dict(manifest)
    result.update({
        "output_path": str(output),
        "archive_bytes": len(data),
        "archive_sha256": hashlib.sha256(data).hexdigest(),
    })
    return result


def read_bundle_manifest(bundle_path):
    bundle = Path(bundle_path).resolve()
    with zipfile.ZipFile(bundle) as archive:
        if BUNDLE_MANIFEST_PATH not in archive.namelist():
            raise ValueError("Bundle manifest not found: %s" % BUNDLE_MANIFEST_PATH)
        manifest = json.loads(archive.read(BUNDLE_MANIFEST_PATH).decode("utf-8-sig"))
    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise ValueError("Unsupported bundle schema: %s" % manifest.get("schema_version"))
    return manifest


def verify_bundle(bundle_path):
    bundle = Path(bundle_path).resolve()
    issues = []
    try:
        manifest = read_bundle_manifest(bundle)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        return _verify_result(bundle, None, [{"code": "bundle_read_error", "message": str(exc)}])

    try:
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            package = manifest.get("package") or {}
            if package.get("runtime_api") != RUNTIME_API_VERSION:
                issues.append({
                    "code": "unsupported_runtime_api",
                    "message": "unsupported runtime api: %s" % package.get("runtime_api"),
                    "path": BUNDLE_MANIFEST_PATH,
                })
            for entry in manifest.get("entries", []):
                path = entry.get("path")
                kind = entry.get("kind")
                if not _is_safe_archive_path(path):
                    issues.append({"code": "unsafe_path", "message": "unsafe bundle path: %r" % path, "path": path})
                    continue
                if path not in names:
                    issues.append({"code": "missing_entry", "message": "missing bundle entry: %s" % path, "path": path})
                    continue
                if kind == "bundle_manifest":
                    continue
                data = archive.read(path)
                expected_bytes = entry.get("bytes")
                expected_sha = entry.get("sha256")
                if expected_bytes is not None and len(data) != expected_bytes:
                    issues.append({"code": "bytes_mismatch", "message": "byte size mismatch: %s" % path, "path": path})
                if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
                    issues.append({"code": "sha256_mismatch", "message": "sha256 mismatch: %s" % path, "path": path})
            manifest_paths = {entry.get("path") for entry in manifest.get("entries", [])}
            for name in names:
                if name not in manifest_paths:
                    issues.append({"code": "unlisted_entry", "message": "bundle contains unlisted entry: %s" % name, "path": name})
    except (OSError, zipfile.BadZipFile) as exc:
        issues.append({"code": "bundle_verify_error", "message": str(exc)})
    return _verify_result(bundle, manifest, issues)


def bundle_payloads(bundle_path):
    manifest = read_bundle_manifest(bundle_path)
    payloads = []
    with zipfile.ZipFile(Path(bundle_path).resolve()) as archive:
        for entry in manifest.get("entries", []):
            kind = entry.get("kind")
            path = entry.get("path")
            if kind in ("runtime_file", "scaffold_file"):
                payloads.append((kind, path, archive.read(path)))
    return manifest, payloads


def _verify_result(bundle, manifest, issues):
    data = bundle.read_bytes() if bundle.exists() and bundle.is_file() else b""
    return {
        "schema_version": BUNDLE_VERIFY_SCHEMA_VERSION,
        "ok": not issues,
        "bundle_path": str(bundle),
        "archive_bytes": len(data),
        "archive_sha256": hashlib.sha256(data).hexdigest() if data else None,
        "issue_count": len(issues),
        "issues": issues,
        "manifest": manifest,
    }


def _is_safe_archive_path(path):
    if not isinstance(path, str) or not path:
        return False
    if path.startswith("/") or path.startswith("\\"):
        return False
    parts = path.replace("\\", "/").split("/")
    return ".." not in parts and all(parts)


def _runtime_file_payloads(manifest):
    # Manifest paths describe the *install target* layout; the source files
    # live flat next to this module (agent-stack-shared/pylib/ue_runtime).
    source_root = Path(__file__).resolve().parent
    payloads = {}
    for entry in manifest["entries"]:
        if entry["kind"] != "runtime_file":
            continue
        rel_path = entry["path"]
        payloads[rel_path] = (source_root / Path(rel_path).name).read_bytes()
    return payloads
