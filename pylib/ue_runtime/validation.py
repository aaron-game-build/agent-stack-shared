"""
Registry validation helpers.

Keep validation here instead of in the CLI so external services can verify a
task catalog without shelling out to project-specific scripts.
"""

from dataclasses import dataclass
from pathlib import Path


VALIDATION_SCHEMA_VERSION = "ue-task-validation/v1"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    task_id: str = ""
    severity: str = "error"

    def as_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "task_id": self.task_id,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issue_count: int
    issues: tuple

    def as_dict(self):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "ok": self.ok,
            "issue_count": self.issue_count,
            "issues": [issue.as_dict() for issue in self.issues],
        }

    def messages(self):
        return [issue.message for issue in self.issues]


def validate_registry(registry, context=None, repo_root=None, source_root=None):
    return validate_registry_report(
        registry,
        context=context,
        repo_root=repo_root,
        source_root=source_root,
    ).messages()


def validate_registry_report(registry, context=None, repo_root=None, source_root=None):
    tasks = registry.list() if hasattr(registry, "list") else list(registry)
    root = Path(repo_root or (context.repo_root if context else ".")).resolve()
    source = Path(source_root).resolve() if source_root else root / "Content" / "Python"

    issues = []
    seen = set()
    for task in tasks:
        if task.task_id in seen:
            issues.append(_issue("duplicate_task_id", "duplicate task id: %s" % task.task_id, task.task_id))
        seen.add(task.task_id)

        try:
            task.validate()
        except Exception as exc:
            issues.append(_issue("invalid_task", "%s invalid: %s" % (task.task_id, exc), task.task_id))

        if task.old_entrypoint:
            path = root / task.old_entrypoint.replace("\\", "/")
            if not path.exists():
                issues.append(_issue(
                    "missing_old_entrypoint",
                    "%s missing old_entrypoint: %s" % (task.task_id, task.old_entrypoint),
                    task.task_id,
                ))

        standalone_entrypoint = task.effective_standalone_entrypoint()
        if standalone_entrypoint and standalone_entrypoint != task.old_entrypoint:
            path = root / str(standalone_entrypoint).replace("\\", "/")
            if not path.exists():
                issues.append(_issue(
                    "missing_standalone_entrypoint",
                    "%s missing standalone_entrypoint: %s" % (task.task_id, standalone_entrypoint),
                    task.task_id,
                ))

        if task.module and not _module_exists(source, task.module):
            issues.append(_issue(
                "missing_module",
                "%s missing module file: %s" % (task.task_id, task.module),
                task.task_id,
            ))

        if task.requires_pie and task.level != "L4":
            issues.append(_issue("pie_level_mismatch", "%s requires PIE but is not level L4" % task.task_id, task.task_id))
        if task.mutates_assets and not task.requires_editor:
            issues.append(_issue(
                "asset_mutation_without_editor",
                "%s mutates assets but does not require Editor" % task.task_id,
                task.task_id,
            ))
        if task.effective_execution_mode() == "local" and task.requires_editor:
            issues.append(_issue(
                "local_mode_requires_editor",
                "%s requires Editor but execution_mode is local" % task.task_id,
                task.task_id,
            ))
        if task.effective_execution_strategy() == "editor_cmd_python" and task.effective_execution_mode() == "local":
            issues.append(_issue(
                "standalone_strategy_local_mode",
                "%s uses editor_cmd_python but execution_mode is local" % task.task_id,
                task.task_id,
            ))
        if task.effective_risk() == "read_only" and task.mutates_assets:
            issues.append(_issue(
                "read_only_mutates_assets",
                "%s mutates assets but risk is read_only" % task.task_id,
                task.task_id,
            ))
        for field_name in ("kb_refs", "required_reading"):
            for rel_doc in getattr(task, field_name, ()):
                path = root / str(rel_doc).replace("\\", "/")
                if not path.exists():
                    issues.append(_issue(
                        "missing_%s" % field_name,
                        "%s %s missing: %s" % (task.task_id, field_name, rel_doc),
                        task.task_id,
                    ))

    issue_tuple = tuple(issues)
    return ValidationReport(ok=not issue_tuple, issue_count=len(issue_tuple), issues=issue_tuple)


def _module_exists(source_root, dotted_module):
    module_path = source_root.joinpath(*dotted_module.split(".")).with_suffix(".py")
    package_path = source_root.joinpath(*dotted_module.split("."), "__init__.py")
    return module_path.exists() or package_path.exists()


def _issue(code, message, task_id):
    return ValidationIssue(code=code, message=message, task_id=task_id)
