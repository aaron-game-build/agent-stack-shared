"""
Shared task runtime for project Python automation.

The package is intentionally UE-light: it can describe, list, and dry-run tasks
from a normal Python process, while task execution may still enter UE Python
modules when the selected task requires the Editor.
"""

from ue_runtime.boundary import (
    BOUNDARY_SCHEMA_VERSION,
    BoundaryIssue,
    BoundaryReport,
    check_runtime_boundary,
)
from ue_runtime.advisor import (
    GROUP_SCHEMA_VERSION,
    HEALTH_SCHEMA_VERSION,
    RECOMMEND_SCHEMA_VERSION,
    SAFE_RUN_SCHEMA_VERSION,
    group_report,
    health_report,
    recommend_tasks,
    safe_run_plan,
)
from ue_runtime.bundle import (
    BUNDLE_SCHEMA_VERSION,
    BUNDLE_VERIFY_SCHEMA_VERSION,
    build_bundle_manifest,
    read_bundle_manifest,
    verify_bundle,
    write_bundle,
)
from ue_runtime.context import RuntimeContext
from ue_runtime.discovery import discover_root_tasks
from ue_runtime.install_audit import INSTALL_AUDIT_SCHEMA_VERSION, audit_runtime_install
from ue_runtime.install_plan import INSTALL_PLAN_SCHEMA_VERSION, build_install_plan
from ue_runtime.installer import (
    INSTALL_RECEIPT_PATH,
    INSTALL_RECEIPT_SCHEMA_VERSION,
    INSTALL_RESULT_SCHEMA_VERSION,
    install_project,
)
from ue_runtime.manifest import build_manifest
from ue_runtime.package import (
    MIN_COMPATIBLE_RUNTIME_VERSION,
    PACKAGE_NAME,
    PACKAGE_SCHEMA_VERSION,
    RUNTIME_API_VERSION,
    RUNTIME_VERSION,
    build_package_manifest,
    package_file_names,
    runtime_metadata,
)
from ue_runtime.protocol import (
    SERVICE_CAPABILITIES,
    SERVICE_COMMANDS,
    SERVICE_PROTOCOL_VERSION,
    build_service_descriptor,
)
from ue_runtime.readiness import (
    READINESS_SCHEMA_VERSION,
    ReadinessIssue,
    ReadinessReport,
    check_runtime_readiness,
)
from ue_runtime.registry import TaskRegistry
from ue_runtime.runner import TaskRunner
from ue_runtime.scaffold import (
    SCAFFOLD_SCHEMA_VERSION,
    build_project_scaffold,
    scaffold_file_names,
)
from ue_runtime.smoke import SMOKE_SCHEMA_VERSION, run_runtime_smoke
from ue_runtime.service import (
    DEFAULT_REGISTRY_FACTORY,
    REGISTRY_FACTORY_ENV,
    REPO_ROOT_ENV,
    TaskService,
    load_registry,
    resolve_registry_factory,
    resolve_repo_root,
)
from ue_runtime.schemas import (
    SCHEMA_REGISTRY_VERSION,
    build_schema_document,
    build_schema_registry,
    schema_names,
)
from ue_runtime.task import ExecutionMode, TaskKind, TaskLevel, TaskRisk, TaskSpec
from ue_runtime.validation import (
    VALIDATION_SCHEMA_VERSION,
    ValidationIssue,
    ValidationReport,
    validate_registry,
    validate_registry_report,
)

__all__ = [
    "DEFAULT_REGISTRY_FACTORY",
    "PACKAGE_NAME",
    "PACKAGE_SCHEMA_VERSION",
    "RUNTIME_API_VERSION",
    "RUNTIME_VERSION",
    "MIN_COMPATIBLE_RUNTIME_VERSION",
    "INSTALL_PLAN_SCHEMA_VERSION",
    "INSTALL_AUDIT_SCHEMA_VERSION",
    "INSTALL_RECEIPT_SCHEMA_VERSION",
    "INSTALL_RECEIPT_PATH",
    "INSTALL_RESULT_SCHEMA_VERSION",
    "BUNDLE_SCHEMA_VERSION",
    "BUNDLE_VERIFY_SCHEMA_VERSION",
    "REGISTRY_FACTORY_ENV",
    "REPO_ROOT_ENV",
    "BOUNDARY_SCHEMA_VERSION",
    "HEALTH_SCHEMA_VERSION",
    "GROUP_SCHEMA_VERSION",
    "RECOMMEND_SCHEMA_VERSION",
    "SAFE_RUN_SCHEMA_VERSION",
    "READINESS_SCHEMA_VERSION",
    "SERVICE_CAPABILITIES",
    "SERVICE_COMMANDS",
    "SERVICE_PROTOCOL_VERSION",
    "SCHEMA_REGISTRY_VERSION",
    "SCAFFOLD_SCHEMA_VERSION",
    "SMOKE_SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "ExecutionMode",
    "TaskKind",
    "TaskLevel",
    "TaskRegistry",
    "TaskRunner",
    "TaskRisk",
    "TaskSpec",
    "RuntimeContext",
    "TaskService",
    "ValidationIssue",
    "ValidationReport",
    "ReadinessIssue",
    "ReadinessReport",
    "BoundaryIssue",
    "BoundaryReport",
    "build_bundle_manifest",
    "build_install_plan",
    "build_manifest",
    "build_package_manifest",
    "build_project_scaffold",
    "build_schema_document",
    "build_schema_registry",
    "build_service_descriptor",
    "check_runtime_boundary",
    "check_runtime_readiness",
    "discover_root_tasks",
    "group_report",
    "health_report",
    "install_project",
    "audit_runtime_install",
    "load_registry",
    "resolve_registry_factory",
    "resolve_repo_root",
    "read_bundle_manifest",
    "package_file_names",
    "runtime_metadata",
    "recommend_tasks",
    "run_runtime_smoke",
    "safe_run_plan",
    "scaffold_file_names",
    "schema_names",
    "validate_registry",
    "validate_registry_report",
    "verify_bundle",
    "write_bundle",
]
