"""
Service descriptor for external task-runtime integrations.

This module is the lightweight handshake layer: external tools can inspect the
runtime protocol, schema versions, project binding, and supported operations
before deciding which catalog or command endpoint to consume.
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
from ue_runtime.package import PACKAGE_SCHEMA_VERSION, runtime_metadata
from ue_runtime.readiness import READINESS_SCHEMA_VERSION
from ue_runtime.scaffold import SCAFFOLD_SCHEMA_VERSION
from ue_runtime.smoke import SMOKE_SCHEMA_VERSION
from ue_runtime.validation import VALIDATION_SCHEMA_VERSION


SERVICE_PROTOCOL_VERSION = "ue-task-runtime-service/v1"


SERVICE_CAPABILITIES = (
    "task_catalog",
    "task_manifest",
    "filtered_catalog",
    "task_plan",
    "task_command",
    "standalone_editor_runner",
    "policy_gate",
    "dry_run",
    "registry_validation",
    "runtime_readiness",
    "runtime_boundary_check",
    "runtime_package_manifest",
    "runtime_install_plan",
    "runtime_install_audit",
    "runtime_smoke",
    "runtime_health",
    "task_grouping",
    "task_recommendations",
    "safe_run",
    "project_tool_wrappers",
    "script_kb_map",
    "runtime_installer",
    "runtime_installer_post_verify",
    "runtime_bundle",
    "runtime_bundle_verify",
    "schema_registry",
    "project_scaffold",
    "service_descriptor",
)


SERVICE_COMMANDS = (
    {"name": "about", "json": True, "description": "Describe service protocol and project binding."},
    {"name": "list", "json": False, "description": "List registered task summaries."},
    {"name": "show", "json": True, "description": "Describe one task."},
    {"name": "plan", "json": True, "description": "Describe execution plan for one task, including standalone UnrealEditor-Cmd runners when declared or inferred."},
    {"name": "command", "json": True, "description": "Render an executable command for one task; standalone editor runners prefer UnrealEditor-Cmd over shared Remote Exec."},
    {"name": "gate", "json": True, "description": "Evaluate one task against risk and execution budgets."},
    {"name": "run", "json": False, "description": "Run or dry-run one task."},
    {"name": "manifest", "json": True, "description": "Render machine-readable task catalog."},
    {"name": "policy", "json": True, "description": "Summarize task policy distribution."},
    {"name": "validate", "json": True, "description": "Validate registry metadata."},
    {"name": "boundary", "json": True, "description": "Check portable runtime boundary hygiene."},
    {"name": "smoke", "json": True, "description": "Run the standard installed-project smoke checks."},
    {"name": "health", "json": True, "description": "Run the recommended Agent health check chain."},
    {"name": "group", "json": True, "description": "List a task group by kind, execution mode, execution strategy, risk, or tag; supports aliases such as standalone/runner/remote."},
    {"name": "recommend", "json": True, "description": "Recommend tasks for a goal string, including execution_mode/execution_strategy-aware matches."},
    {"name": "safe-run", "json": True, "description": "Gate, plan, and optionally run a safe local task; reports execution_mode and execution_strategy at the top level."},
    {"name": "inventory", "json": False, "description": "Run the project script inventory helper."},
    {"name": "arch-audit", "json": True, "description": "Run the project architecture audit helper."},
    {"name": "adoption-check", "json": True, "description": "Run the cross-project adoption smoke helper."},
    {"name": "kb-map", "json": True, "description": "Run the project script-to-KB map helper."},
    {"name": "schema", "json": True, "description": "Describe runtime JSON contracts."},
    {"name": "scaffold", "json": True, "description": "Render files for a new project binding."},
    {"name": "package", "json": True, "description": "Describe portable runtime package files."},
    {"name": "install-plan", "json": True, "description": "Render a dry-run cross-project install plan."},
    {"name": "install-audit", "json": True, "description": "Audit an installed runtime copy for drift."},
    {"name": "install", "json": True, "description": "Dry-run or apply the runtime into a target project; --verify runs generated smoke commands after apply."},
    {"name": "bundle", "json": True, "description": "Describe or write a portable runtime zip bundle."},
    {"name": "bundle-verify", "json": True, "description": "Verify a portable runtime zip bundle."},
    {"name": "doctor", "json": True, "description": "Check project service-readiness."},
)


def build_service_descriptor(service):
    manifest = service.manifest()
    readiness = service.readiness_report()
    context = service.context
    config = context.config if context else {}
    project = dict(manifest.get("project") or {})
    project["bootstrap_scripts"] = context.task_runtime_bootstrap_scripts() if context else []
    runtime = runtime_metadata()

    return {
        "schema_version": SERVICE_PROTOCOL_VERSION,
        "schemas": {
            "manifest": MANIFEST_SCHEMA_VERSION,
            "readiness": READINESS_SCHEMA_VERSION,
            "validation": VALIDATION_SCHEMA_VERSION,
            "boundary": BOUNDARY_SCHEMA_VERSION,
            "smoke": SMOKE_SCHEMA_VERSION,
            "health": HEALTH_SCHEMA_VERSION,
            "group": GROUP_SCHEMA_VERSION,
            "recommend": RECOMMEND_SCHEMA_VERSION,
            "safe_run": SAFE_RUN_SCHEMA_VERSION,
            "package": PACKAGE_SCHEMA_VERSION,
            "install_plan": INSTALL_PLAN_SCHEMA_VERSION,
            "install_audit": INSTALL_AUDIT_SCHEMA_VERSION,
            "install_result": INSTALL_RESULT_SCHEMA_VERSION,
            "bundle": BUNDLE_SCHEMA_VERSION,
            "bundle_verify": BUNDLE_VERIFY_SCHEMA_VERSION,
            "schema_registry": "ue-task-runtime-schemas/v1",
            "scaffold": SCAFFOLD_SCHEMA_VERSION,
        },
        "capabilities": list(SERVICE_CAPABILITIES),
        "commands": list(SERVICE_COMMANDS),
        "registry_factory": service.registry_factory,
        "runtime": runtime,
        "project": project,
        "task_count": manifest.get("task_count", 0),
        "summary": manifest.get("summary", {}),
        "readiness": {
            "ok": readiness.ok,
            "issue_count": readiness.issue_count,
            "error_count": readiness.error_count,
            "warning_count": readiness.warning_count,
        },
        "environment": {
            "project_name": config.get("project_name"),
            "ue_python_script": config.get("ue_python_script"),
        },
    }
