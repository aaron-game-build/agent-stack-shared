"""
Portable package manifest for distributing the task runtime.

This module describes the files that make up ``ue_runtime`` so another project
can copy and verify the shared service layer without pulling project-specific task
bindings along with it.
"""

import hashlib
from pathlib import Path


PACKAGE_SCHEMA_VERSION = "ue-task-runtime-package/v1"
PACKAGE_NAME = "ue-runtime"
RUNTIME_API_VERSION = "ue-task-runtime/v1"
RUNTIME_VERSION = "0.1.0"
MIN_COMPATIBLE_RUNTIME_VERSION = "0.1.0"


def runtime_metadata():
    return {
        "package": PACKAGE_NAME,
        "runtime_version": RUNTIME_VERSION,
        "runtime_api": RUNTIME_API_VERSION,
        "compatibility": {
            "minimum_runtime_version": MIN_COMPATIBLE_RUNTIME_VERSION,
            "package_schema_version": PACKAGE_SCHEMA_VERSION,
        },
    }


def build_package_manifest(runtime_root=None):
    root = Path(runtime_root or Path(__file__).resolve().parent)
    files = []
    for path in sorted(root.glob("*.py")):
        if path.name == "__pycache__":
            continue
        data = path.read_bytes()
        files.append({
            "path": "Content/Python/ue_runtime/%s" % path.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package": PACKAGE_NAME,
        "runtime_version": RUNTIME_VERSION,
        "runtime_api": RUNTIME_API_VERSION,
        "compatibility": runtime_metadata()["compatibility"],
        "runtime_path": "Content/Python/ue_runtime",
        "file_count": len(files),
        "files": files,
        "install": {
            "copy_roots": [
                "Content/Python/ue_runtime",
            ],
            "project_binding": [
                "Content/Python/<project_registry_package>/registry.py",
                "scripts/<project_task_bootstrap>.py",
                "scripts/<project_task_bootstrap>.ps1",
                ".ue-py-config.json task_runtime.registry_factory",
                ".ue-task-runtime-install.json",
            ],
            "verify_commands": [
                "python scripts/<project_task_bootstrap>.py about --json",
                "python scripts/<project_task_bootstrap>.py boundary --json",
                "python scripts/<project_task_bootstrap>.py validate --json",
                "python scripts/<project_task_bootstrap>.py doctor --json",
                "python scripts/<project_task_bootstrap>.py install-audit --target-root . --json",
                "python scripts/<project_task_bootstrap>.py smoke --target-root . --json",
            ],
        },
    }


def package_file_names(runtime_root=None):
    return tuple(file["path"] for file in build_package_manifest(runtime_root)["files"])
