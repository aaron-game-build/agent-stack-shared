"""
Controlled installer for adopting the portable task runtime in a project.

The installer is safe by default: callers get a dry-run result unless they pass
``apply=True``. When applying, existing files with different content are treated
as conflicts unless ``force=True`` is explicit.
"""

import json
import subprocess
import sys
from pathlib import Path

from ue_runtime.bundle import bundle_payloads, verify_bundle
from ue_runtime.install_plan import build_install_plan
from ue_runtime.package import build_package_manifest
from ue_runtime.scaffold import build_project_scaffold


INSTALL_RESULT_SCHEMA_VERSION = "ue-task-runtime-install-result/v1"
INSTALL_RECEIPT_SCHEMA_VERSION = "ue-task-runtime-install-receipt/v1"
INSTALL_RECEIPT_PATH = ".ue-task-runtime-install.json"


def install_project(
    target_root,
    project_name="ExampleProject",
    registry_module="project_tasks.registry",
    bootstrap_name="task.py",
    apply=False,
    force=False,
    bundle_path=None,
    verify=False,
):
    target_root = Path(target_root).resolve()
    bundle_report = None
    if bundle_path:
        source = "bundle"
        bundle_report = verify_bundle(bundle_path)
        if not bundle_report["ok"]:
            return _failed_bundle_result(target_root, bundle_report, apply=apply, force=force, verify=verify)
        bundle_manifest, payloads = bundle_payloads(bundle_path)
        scaffold_config = _bundle_scaffold_config(payloads)
        project_name = bundle_manifest["scaffold"]["project_name"]
        registry_factory = bundle_manifest["scaffold"]["registry_factory"]
        plan = _bundle_install_plan(bundle_manifest)
        verify_commands = list(bundle_manifest.get("verify_commands") or [])
        receipt = _bundle_install_receipt(bundle_manifest, source)
    else:
        plan = build_install_plan(
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
        )
        package = build_package_manifest()
        scaffold = build_project_scaffold(
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
        )
        runtime_files = _runtime_file_payloads(package)
        scaffold_files = {
            path: content.encode("utf-8")
            for path, content in scaffold["files"].items()
        }
        payloads = []
        for rel_path, data in runtime_files.items():
            payloads.append(("runtime_file", rel_path, data))
        for rel_path, data in scaffold_files.items():
            payloads.append(("scaffold_file", rel_path, data))
        scaffold_config = json.loads(scaffold["files"][".ue-py-config.task-runtime.json"])
        registry_factory = scaffold["registry_factory"]
        verify_commands = list(scaffold["next_commands"])
        source = "source_tree"
        receipt = _source_install_receipt(package, scaffold, source)

    actions = []
    conflicts = []
    for kind, rel_path, data in payloads:
        target = target_root / rel_path
        status = _planned_file_status(target, data, apply=apply, force=force)
        action = _action(kind, rel_path, status)
        actions.append(action)
        if status == "conflict":
            conflicts.append(action)

    config_action, config_conflict = _plan_config_merge(
        target_root / ".ue-py-config.json",
        scaffold_config,
        apply=apply,
        force=force,
    )
    actions.append(config_action)
    if config_conflict:
        conflicts.append(config_action)

    receipt_data = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    receipt_status = _planned_file_status(target_root / INSTALL_RECEIPT_PATH, receipt_data, apply=apply, force=force)
    receipt_action = _action("install_receipt", INSTALL_RECEIPT_PATH, receipt_status)
    actions.append(receipt_action)
    if receipt_status == "conflict":
        conflicts.append(receipt_action)

    ok = not conflicts
    applied = bool(apply and ok)
    if applied:
        for _, rel_path, data in payloads:
            target = target_root / rel_path
            _write_bytes(target, data)
        _apply_config_merge(
            target_root / ".ue-py-config.json",
            scaffold_config,
            force=force,
        )
        _write_bytes(target_root / INSTALL_RECEIPT_PATH, receipt_data)
        actions = [_applied_action(action) for action in actions]
    post_verify = _post_verify_result(
        target_root,
        verify_commands,
        requested=verify,
        applied=applied,
    )
    if verify and post_verify and not post_verify["ok"]:
        ok = False

    return {
        "schema_version": INSTALL_RESULT_SCHEMA_VERSION,
        "ok": ok,
        "dry_run": not apply,
        "applied": applied,
        "force": bool(force),
        "source": source,
        "bundle": bundle_report,
        "target_root": str(target_root),
        "project_name": project_name,
        "registry_factory": registry_factory,
        "receipt": receipt,
        "plan": plan,
        "action_count": len(actions),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "actions": actions,
        "verify_commands": verify_commands,
        "post_verify": post_verify,
    }


def _runtime_file_payloads(package):
    # Manifest paths describe the *install target* layout; the source files
    # live flat next to this module (agent-stack-shared/pylib/ue_runtime).
    source_root = Path(__file__).resolve().parent
    payloads = {}
    for record in package["files"]:
        rel_path = record["path"]
        payloads[rel_path] = (source_root / Path(rel_path).name).read_bytes()
    return payloads


def _bundle_scaffold_config(payloads):
    for kind, path, data in payloads:
        if kind == "scaffold_file" and path == ".ue-py-config.task-runtime.json":
            return json.loads(data.decode("utf-8-sig"))
    raise ValueError("Bundle does not include .ue-py-config.task-runtime.json")


def _bundle_install_plan(bundle_manifest):
    return {
        "schema_version": "ue-task-runtime-install-plan/v1",
        "project_name": bundle_manifest["scaffold"]["project_name"],
        "registry_factory": bundle_manifest["scaffold"]["registry_factory"],
        "package": dict(bundle_manifest["package"]),
        "scaffold": dict(bundle_manifest["scaffold"]),
        "operations": [
            {
                "order": 1,
                "action": "verify_bundle",
                "source": bundle_manifest["manifest_path"],
                "verification": "bundle hashes match manifest",
            },
            {
                "order": 2,
                "action": "write_files",
                "file_count": len([
                    entry for entry in bundle_manifest["entries"]
                    if entry["kind"] in ("runtime_file", "scaffold_file")
                ]),
                "verification": "file contents equal bundle entries",
            },
            {
                "order": 3,
                "action": "merge_config",
                "source": ".ue-py-config.task-runtime.json",
                "target": ".ue-py-config.json",
                "verification": "doctor --json returns ok",
            },
            {
                "order": 4,
                "action": "write_receipt",
                "target": INSTALL_RECEIPT_PATH,
                "verification": "install-audit --json reports receipt ok after apply",
            },
            {
                "order": 5,
                "action": "run_verify_commands",
                "commands": list(bundle_manifest.get("verify_commands") or []),
                "verification": "all commands exit 0",
            },
        ],
        "verify_commands": list(bundle_manifest.get("verify_commands") or []),
    }


def _source_install_receipt(package, scaffold, source):
    return {
        "schema_version": INSTALL_RECEIPT_SCHEMA_VERSION,
        "source": source,
        "package": _package_summary(package),
        "project_name": scaffold["project_name"],
        "registry_factory": scaffold["registry_factory"],
        "bootstrap_scripts": list(scaffold["bootstrap_scripts"]),
        "runtime_files": list(package.get("files") or []),
        "scaffold_files": sorted(scaffold["files"]),
    }


def _bundle_install_receipt(bundle_manifest, source):
    runtime_files = [
        {
            "path": entry["path"],
            "sha256": entry.get("sha256"),
            "bytes": entry.get("bytes"),
        }
        for entry in bundle_manifest.get("entries", [])
        if entry.get("kind") == "runtime_file"
    ]
    return {
        "schema_version": INSTALL_RECEIPT_SCHEMA_VERSION,
        "source": source,
        "package": dict(bundle_manifest["package"]),
        "project_name": bundle_manifest["scaffold"]["project_name"],
        "registry_factory": bundle_manifest["scaffold"]["registry_factory"],
        "bootstrap_scripts": list(bundle_manifest["scaffold"].get("bootstrap_scripts") or []),
        "runtime_files": runtime_files,
        "scaffold_files": list(bundle_manifest["scaffold"].get("files") or []),
        "bundle": {
            "schema_version": bundle_manifest.get("schema_version"),
            "entry_count": bundle_manifest.get("entry_count"),
            "manifest_path": bundle_manifest.get("manifest_path"),
        },
    }


def _package_summary(package):
    return {
        "schema_version": package.get("schema_version"),
        "package": package.get("package"),
        "runtime_version": package.get("runtime_version"),
        "runtime_api": package.get("runtime_api"),
        "compatibility": dict(package.get("compatibility") or {}),
        "runtime_path": package.get("runtime_path"),
        "file_count": package.get("file_count"),
    }


def _failed_bundle_result(target_root, bundle_report, apply=False, force=False, verify=False):
    return {
        "schema_version": INSTALL_RESULT_SCHEMA_VERSION,
        "ok": False,
        "dry_run": not apply,
        "applied": False,
        "force": bool(force),
        "source": "bundle",
        "bundle": bundle_report,
        "target_root": str(target_root),
        "project_name": None,
        "registry_factory": None,
        "receipt": None,
        "plan": None,
        "action_count": 0,
        "conflict_count": bundle_report["issue_count"],
        "conflicts": bundle_report["issues"],
        "actions": [],
        "verify_commands": [],
        "post_verify": _post_verify_result(
            target_root,
            [],
            requested=verify,
            applied=False,
            skip_reason="bundle verification failed",
        ),
    }


def _planned_file_status(target, data, apply=False, force=False):
    if not target.exists():
        return "planned" if not apply else "write"
    if not target.is_file():
        return "conflict"
    if target.read_bytes() == data:
        return "unchanged"
    if force:
        return "planned_overwrite" if not apply else "overwrite"
    return "conflict"


def _plan_config_merge(config_path, desired, apply=False, force=False):
    if not config_path.exists():
        return _action("config_merge", ".ue-py-config.json", "planned" if not apply else "write"), False
    if not config_path.is_file():
        return _action("config_merge", ".ue-py-config.json", "conflict"), True
    try:
        existing = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        status = "planned_overwrite" if force and not apply else "overwrite" if force else "conflict"
        return _action("config_merge", ".ue-py-config.json", status), not force
    conflict = _config_has_conflict(existing, desired, force=force)
    if conflict:
        return _action("config_merge", ".ue-py-config.json", "conflict"), True
    merged = _merged_config(existing, desired, force=force)
    status = "unchanged" if merged == existing else "planned" if not apply else "merge"
    return _action("config_merge", ".ue-py-config.json", status), False


def _config_has_conflict(existing, desired, force=False):
    if force:
        return False
    project_name = existing.get("project_name")
    if project_name and project_name != desired.get("project_name"):
        return True
    task_runtime = existing.get("task_runtime")
    if task_runtime is not None and not isinstance(task_runtime, dict):
        return True
    task_runtime = task_runtime or {}
    registry_factory = task_runtime.get("registry_factory")
    desired_factory = desired["task_runtime"]["registry_factory"]
    if registry_factory and registry_factory != desired_factory:
        return True
    bootstrap_scripts = task_runtime.get("bootstrap_scripts")
    return bootstrap_scripts is not None and not isinstance(bootstrap_scripts, list)


def _merged_config(existing, desired, force=False):
    merged = dict(existing)
    if force or not merged.get("project_name"):
        merged["project_name"] = desired["project_name"]
    task_runtime = dict(merged.get("task_runtime") or {})
    desired_runtime = desired["task_runtime"]
    if force or not task_runtime.get("registry_factory"):
        task_runtime["registry_factory"] = desired_runtime["registry_factory"]
    scripts = list(task_runtime.get("bootstrap_scripts") or [])
    for script in desired_runtime["bootstrap_scripts"]:
        if script not in scripts:
            scripts.append(script)
    task_runtime["bootstrap_scripts"] = scripts
    merged["task_runtime"] = task_runtime
    return merged


def _apply_config_merge(config_path, desired, force=False):
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            existing = {}
    else:
        existing = {}
    merged = _merged_config(existing, desired, force=force)
    _write_text(config_path, json.dumps(merged, indent=2, sort_keys=True) + "\n")


def _applied_action(action):
    status_map = {
        "planned": "written",
        "write": "written",
        "planned_overwrite": "overwritten",
        "overwrite": "overwritten",
        "merge": "merged",
    }
    updated = dict(action)
    updated["status"] = status_map.get(action["status"], action["status"])
    return updated


def _write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _post_verify_result(target_root, commands, requested=False, applied=False, skip_reason=None):
    if not requested:
        return {
            "requested": False,
            "skipped": True,
            "ok": True,
            "reason": "not requested",
            "command_count": len(commands),
            "results": [],
        }
    if not applied:
        return {
            "requested": True,
            "skipped": True,
            "ok": False,
            "reason": skip_reason or "install was not applied",
            "command_count": len(commands),
            "results": [],
        }
    results = []
    for command in commands:
        argv = _verify_command_argv(command)
        completed = subprocess.run(
            argv,
            cwd=target_root,
            text=True,
            capture_output=True,
        )
        results.append({
            "command": command,
            "argv": argv,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        })
    return {
        "requested": True,
        "skipped": False,
        "ok": all(result["ok"] for result in results),
        "reason": "",
        "command_count": len(commands),
        "results": results,
    }


def _verify_command_argv(command):
    parts = command.split()
    if parts and parts[0].lower() == "python":
        parts[0] = sys.executable
    return parts


def _action(kind, rel_path, status):
    return {
        "kind": kind,
        "path": rel_path,
        "status": status,
    }
