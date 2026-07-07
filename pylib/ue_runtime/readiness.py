"""
Project readiness checks for the task runtime service boundary.

Validation answers "is the registry internally correct?". Readiness answers
"can an external service discover and operate this project through the runtime?".
"""

from dataclasses import dataclass

from ue_runtime.boundary import check_runtime_boundary
from ue_runtime.manifest import SCHEMA_VERSION


READINESS_SCHEMA_VERSION = "ue-task-runtime-readiness/v1"


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    severity: str = "error"
    path: str = ""
    task_id: str = ""

    def as_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "path": self.path,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class ReadinessReport:
    ok: bool
    issues: tuple
    registry_factory: str = ""
    task_count: int = 0

    @property
    def issue_count(self):
        return len(self.issues)

    @property
    def error_count(self):
        return len([issue for issue in self.issues if issue.severity == "error"])

    @property
    def warning_count(self):
        return len([issue for issue in self.issues if issue.severity == "warning"])

    def as_dict(self):
        return {
            "schema_version": READINESS_SCHEMA_VERSION,
            "ok": self.ok,
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "registry_factory": self.registry_factory,
            "task_count": self.task_count,
            "issues": [issue.as_dict() for issue in self.issues],
        }

    def messages(self):
        return [issue.message for issue in self.issues]


def check_runtime_readiness(service):
    context = service.context
    registry = service.registry
    issues = []

    if context is None:
        issues.append(_issue(
            "missing_context",
            "TaskService has no RuntimeContext; pass repo_root or context for project readiness checks.",
        ))
        root = None
    else:
        root = context.repo_root
        config_path = root / ".ue-py-config.json"
        source_root = root / "Content" / "Python"
        if not config_path.is_file():
            issues.append(_issue(
                "missing_config",
                "missing project runtime config: .ue-py-config.json",
                severity="warning",
                path=".ue-py-config.json",
            ))
        if not context.task_registry_factory():
            issues.append(_issue(
                "implicit_registry_factory",
                "task_runtime.registry_factory is not configured; runtime is using fallback registry resolution.",
                severity="warning",
                path=".ue-py-config.json",
            ))
        if not source_root.is_dir():
            issues.append(_issue(
                "missing_source_root",
                "missing Python source root: Content/Python",
                path="Content/Python",
            ))

        bootstrap_scripts = context.task_runtime_bootstrap_scripts()
        if not bootstrap_scripts:
            issues.append(_issue(
                "missing_bootstrap_scripts",
                "task_runtime.bootstrap_scripts is not configured; shell users may not have a stable project entrypoint.",
                severity="warning",
                path=".ue-py-config.json",
            ))
        for script in bootstrap_scripts:
            if not (root / script).is_file():
                issues.append(_issue(
                    "missing_bootstrap_script",
                    "configured bootstrap script is missing: %s" % script,
                    severity="warning",
                    path=script,
                ))

        standalone_tasks = [
            task for task in registry.list()
            if getattr(task, "effective_execution_strategy", None)
            and task.effective_execution_strategy() == "editor_cmd_python"
        ]
        if standalone_tasks:
            platform = context.platform_config()
            if not platform.get("engine_root"):
                issues.append(_issue(
                    "missing_engine_root_for_standalone_runner",
                    "standalone UnrealEditor-Cmd runners exist but platforms.<current>.engine_root is not configured.",
                    path=".ue-py-config.json",
                ))
            if not platform.get("project_root"):
                issues.append(_issue(
                    "missing_project_root_for_standalone_runner",
                    "standalone UnrealEditor-Cmd runners exist but platforms.<current>.project_root is not configured.",
                    severity="warning",
                    path=".ue-py-config.json",
                ))
            if not (context.config.get("project_name") or "").strip():
                issues.append(_issue(
                    "missing_project_name_for_standalone_runner",
                    "standalone UnrealEditor-Cmd runners exist but project_name is empty.",
                    path=".ue-py-config.json",
                ))

    validation_report = service.validate_report()
    for validation_issue in validation_report.issues:
        issues.append(ReadinessIssue(
            code="registry_%s" % validation_issue.code,
            message=validation_issue.message,
            severity=validation_issue.severity,
            task_id=validation_issue.task_id,
        ))

    boundary_report = check_runtime_boundary()
    for boundary_issue in boundary_report.issues:
        issues.append(ReadinessIssue(
            code="boundary_%s" % boundary_issue.code,
            message=boundary_issue.message,
            severity=boundary_issue.severity,
            path=boundary_issue.path,
        ))

    task_count = 0
    try:
        manifest = service.manifest()
        task_count = manifest.get("task_count", len(registry))
        if manifest.get("schema_version") != SCHEMA_VERSION:
            issues.append(_issue(
                "manifest_schema_mismatch",
                "manifest schema mismatch: %s" % manifest.get("schema_version"),
            ))
    except Exception as exc:
        issues.append(_issue("manifest_failed", "failed to build task manifest: %s" % exc))
        try:
            task_count = len(registry)
        except Exception:
            task_count = 0

    issue_tuple = tuple(issues)
    return ReadinessReport(
        ok=not [issue for issue in issue_tuple if issue.severity == "error"],
        issues=issue_tuple,
        registry_factory=service.registry_factory or "",
        task_count=task_count,
    )


def _issue(code, message, severity="error", path=""):
    return ReadinessIssue(code=code, message=message, severity=severity, path=path)
