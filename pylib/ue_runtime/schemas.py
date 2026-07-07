"""
Machine-readable schemas for task-runtime JSON contracts.

These are intentionally lightweight descriptors rather than full JSON Schema
draft documents. They keep the service contract discoverable without adding a
runtime dependency.
"""

from ue_runtime.boundary import BOUNDARY_SCHEMA_VERSION
from ue_runtime.bundle import BUNDLE_SCHEMA_VERSION, BUNDLE_VERIFY_SCHEMA_VERSION
from ue_runtime.advisor import (
    GROUP_SCHEMA_VERSION,
    HEALTH_SCHEMA_VERSION,
    RECOMMEND_SCHEMA_VERSION,
    SAFE_RUN_SCHEMA_VERSION,
)
from ue_runtime.install_audit import INSTALL_AUDIT_SCHEMA_VERSION
from ue_runtime.install_plan import INSTALL_PLAN_SCHEMA_VERSION
from ue_runtime.installer import INSTALL_RESULT_SCHEMA_VERSION
from ue_runtime.manifest import SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION
from ue_runtime.package import PACKAGE_SCHEMA_VERSION
from ue_runtime.protocol import SERVICE_PROTOCOL_VERSION
from ue_runtime.readiness import READINESS_SCHEMA_VERSION
from ue_runtime.scaffold import SCAFFOLD_SCHEMA_VERSION
from ue_runtime.smoke import SMOKE_SCHEMA_VERSION
from ue_runtime.validation import VALIDATION_SCHEMA_VERSION


SCHEMA_REGISTRY_VERSION = "ue-task-runtime-schemas/v1"


def build_schema_registry():
    schemas = {
        "service": _schema(
            SERVICE_PROTOCOL_VERSION,
            "Service descriptor returned by about --json.",
            {
                "schema_version": "string",
                "schemas": "object<string,string>",
                "capabilities": "string[]",
                "commands": "command[]",
                "registry_factory": "string",
                "runtime": "runtime_metadata",
                "project": "project_metadata",
                "task_count": "integer",
                "summary": "manifest_summary",
                "readiness": "readiness_summary",
                "environment": "object",
            },
        ),
        "manifest": _schema(
            MANIFEST_SCHEMA_VERSION,
            "Task catalog returned by manifest.",
            {
                "schema_version": "string",
                "registry_factory": "string",
                "project": "project_metadata",
                "policy": "policy_metadata",
                "task_count": "integer",
                "summary": "manifest_summary",
                "tasks": "task[]",
            },
        ),
        "validation": _schema(
            VALIDATION_SCHEMA_VERSION,
            "Registry validation report returned by validate --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "issue_count": "integer",
                "issues": "validation_issue[]",
            },
        ),
        "readiness": _schema(
            READINESS_SCHEMA_VERSION,
            "Project service-readiness report returned by doctor --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "issue_count": "integer",
                "error_count": "integer",
                "warning_count": "integer",
                "registry_factory": "string",
                "task_count": "integer",
                "issues": "readiness_issue[]",
            },
        ),
        "boundary": _schema(
            BOUNDARY_SCHEMA_VERSION,
            "Portable runtime boundary report returned by boundary --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "checked_files": "integer",
                "issue_count": "integer",
                "issues": "boundary_issue[]",
            },
        ),
        "smoke": _schema(
            SMOKE_SCHEMA_VERSION,
            "Aggregated installed-project smoke report returned by smoke --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "target_root": "string",
                "check_count": "integer",
                "checks": "smoke_check[]",
                "reports": "object<string,object>",
            },
        ),
        "health": _schema(
            HEALTH_SCHEMA_VERSION,
            "Agent-oriented health chain returned by health --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "target_root": "string",
                "task_count": "integer",
                "checks": "health_check[]",
                "reports": "object<string,object>",
            },
        ),
        "group": _schema(
            GROUP_SCHEMA_VERSION,
            "Task group report returned by group --json. Each task record carries execution_mode and execution_strategy metadata.",
            {
                "schema_version": "string",
                "group": "string",
                "group_type": "string",
                "task_count": "integer",
                "tasks": "task[]",
            },
        ),
        "recommend": _schema(
            RECOMMEND_SCHEMA_VERSION,
            "Task recommendations returned by recommend --json. Recommended task records carry execution_mode and execution_strategy metadata plus score/matches.",
            {
                "schema_version": "string",
                "query": "string",
                "tokens": "string[]",
                "task_count": "integer",
                "tasks": "recommended_task[]",
            },
        ),
        "safe_run": _schema(
            SAFE_RUN_SCHEMA_VERSION,
            "Gate/plan/command report returned by safe-run --json.",
            {
                "schema_version": "string",
                "task_id": "string",
                "ok": "boolean",
                "execution_mode": "string",
                "execution_strategy": "string",
                "auto_executable": "boolean",
                "gate": "policy_gate",
                "plan": "execution_plan",
                "command": "command|null",
            },
        ),
        "task": _schema(
            "ue-task-spec/v1",
            "Task record shape used inside manifests and show output.",
            {
                "task_id": "string",
                "title": "string",
                "kind": "string",
                "level": "string",
                "module": "string|null",
                "function": "string",
                "root_script": "string|null",
                "old_entrypoint": "string|null",
                "requires_editor": "boolean",
                "requires_pie": "boolean",
                "mutates_assets": "boolean",
                "success_token": "string|null",
                "execution_mode": "string",
                "execution_strategy": "string",
                "standalone_entrypoint": "string|null",
                "risk": "string",
                "tags": "string[]",
                "description": "string",
                "source": "string",
                "kb_refs": "string[]",
                "pitfalls": "string[]",
                "practices": "string[]",
                "required_reading": "string[]",
            },
        ),
        "scaffold": _schema(
            SCAFFOLD_SCHEMA_VERSION,
            "Project binding scaffold returned by scaffold --json.",
            {
                "schema_version": "string",
                "project_name": "string",
                "registry_factory": "string",
                "bootstrap_scripts": "string[]",
                "files": "object<string,string>",
                "next_commands": "string[]",
            },
        ),
        "package": _schema(
            PACKAGE_SCHEMA_VERSION,
            "Portable runtime package manifest returned by package --json.",
            {
                "schema_version": "string",
                "package": "string",
                "runtime_version": "string",
                "runtime_api": "string",
                "compatibility": "runtime_compatibility",
                "runtime_path": "string",
                "file_count": "integer",
                "files": "package_file[]",
                "install": "package_install",
            },
        ),
        "install_plan": _schema(
            INSTALL_PLAN_SCHEMA_VERSION,
            "Dry-run cross-project install plan returned by install-plan --json.",
            {
                "schema_version": "string",
                "project_name": "string",
                "registry_factory": "string",
                "package": "package_summary",
                "scaffold": "scaffold_summary",
                "operations": "install_operation[]",
                "verify_commands": "string[]",
            },
        ),
        "install_audit": _schema(
            INSTALL_AUDIT_SCHEMA_VERSION,
            "Read-only installed runtime drift report returned by install-audit --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "target_root": "string",
                "package": "package_summary",
                "summary": "install_audit_summary",
                "receipt": "install_receipt_summary",
                "issue_count": "integer",
                "issues": "install_audit_issue[]",
            },
        ),
        "install_result": _schema(
            INSTALL_RESULT_SCHEMA_VERSION,
            "Dry-run or applied cross-project install result returned by install --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "dry_run": "boolean",
                "applied": "boolean",
                "force": "boolean",
                "source": "string",
                "bundle": "bundle_verify|null",
                "target_root": "string",
                "project_name": "string",
                "registry_factory": "string",
                "receipt": "install_receipt|null",
                "plan": "install_plan",
                "action_count": "integer",
                "conflict_count": "integer",
                "conflicts": "install_action[]",
                "actions": "install_action[]",
                "verify_commands": "string[]",
                "post_verify": "install_post_verify",
            },
        ),
        "bundle": _schema(
            BUNDLE_SCHEMA_VERSION,
            "Portable runtime zip bundle manifest returned by bundle --json.",
            {
                "schema_version": "string",
                "archive_format": "string",
                "manifest_path": "string",
                "package": "package_summary",
                "scaffold": "bundle_scaffold_summary",
                "entry_count": "integer",
                "entries": "bundle_entry[]",
                "verify_commands": "string[]",
                "output_path": "string|null",
                "archive_bytes": "integer|null",
                "archive_sha256": "string|null",
            },
        ),
        "bundle_verify": _schema(
            BUNDLE_VERIFY_SCHEMA_VERSION,
            "Portable runtime zip bundle verification report returned by bundle-verify --json.",
            {
                "schema_version": "string",
                "ok": "boolean",
                "bundle_path": "string",
                "archive_bytes": "integer",
                "archive_sha256": "string|null",
                "issue_count": "integer",
                "issues": "bundle_issue[]",
                "manifest": "bundle|null",
            },
        ),
    }
    return {
        "schema_version": SCHEMA_REGISTRY_VERSION,
        "schemas": schemas,
    }


def build_schema_document(name):
    registry = build_schema_registry()
    if name == "all":
        return registry
    schemas = registry["schemas"]
    if name not in schemas:
        raise ValueError("Unknown schema %r. Choose one of: %s" % (name, ", ".join(sorted(schemas))))
    return {
        "schema_version": SCHEMA_REGISTRY_VERSION,
        "name": name,
        "schema": schemas[name],
    }


def schema_names():
    return tuple(sorted(build_schema_registry()["schemas"]))


def _schema(schema_version, description, fields):
    return {
        "schema_version": schema_version,
        "description": description,
        "fields": fields,
    }
