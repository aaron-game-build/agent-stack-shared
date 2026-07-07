"""
Stable machine-readable task manifest.

External services should consume this instead of scraping CLI tables or docs.
The output intentionally omits timestamps so generated files stay diff-stable.
"""

from collections import Counter

from ue_runtime.policy import EXECUTION_MODE_ORDER, RISK_ORDER


SCHEMA_VERSION = "ue-task-manifest/v1"


def build_manifest(registry, context=None, registry_factory=None, tasks=None):
    specs = list(tasks) if tasks is not None else registry.list()
    tasks = [task.as_dict() for task in specs]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "registry_factory": registry_factory,
        "project": _project_metadata(context),
        "policy": {
            "execution_mode_order": list(EXECUTION_MODE_ORDER),
            "risk_order": list(RISK_ORDER),
        },
        "task_count": len(tasks),
        "summary": _summary(tasks),
        "tasks": tasks,
    }
    return manifest


def _project_metadata(context):
    if not context:
        return {}
    config = context.config or {}
    return {
        "project_name": config.get("project_name"),
        "repo_root": str(context.repo_root),
        "ue_python_script": config.get("ue_python_script"),
    }


def _summary(tasks):
    return {
        "by_kind": _counts(task["kind"] for task in tasks),
        "by_level": _counts(task["level"] for task in tasks),
        "by_execution_mode": _counts(task["execution_mode"] for task in tasks),
        "by_execution_strategy": _counts(task["execution_strategy"] for task in tasks),
        "by_risk": _counts(task["risk"] for task in tasks),
        "by_source": _counts(task["source"] for task in tasks),
    }


def _counts(values):
    return dict(sorted(Counter(values).items()))
