"""
Agent-oriented helpers for faster and safer task selection.

The helpers stay project-agnostic: they operate on TaskService and task
metadata, not on project-specific script names.
"""

from ue_runtime.task import ExecutionMode, ExecutionStrategy, TaskRisk


HEALTH_SCHEMA_VERSION = "ue-task-runtime-health/v1"
GROUP_SCHEMA_VERSION = "ue-task-runtime-group/v1"
RECOMMEND_SCHEMA_VERSION = "ue-task-runtime-recommendations/v1"
SAFE_RUN_SCHEMA_VERSION = "ue-task-runtime-safe-run/v1"

GROUP_KIND_ALIASES = {
    "audit": "audit",
    "audits": "audit",
    "diagnostic": "diagnostic",
    "diagnostics": "diagnostic",
    "migration": "migration",
    "migrations": "migration",
    "probe": "probe",
    "probes": "probe",
    "repair": "repair",
    "repairs": "repair",
    "setup": "setup",
    "setups": "setup",
    "tool": "tool",
    "tools": "tool",
    "workflow": "workflow",
    "workflows": "workflow",
}

GROUP_STRATEGY_ALIASES = {
    "in_process": ExecutionStrategy.IN_PROCESS,
    "local_process": ExecutionStrategy.IN_PROCESS,
    "remote_exec": ExecutionStrategy.REMOTE_EXEC,
    "remote": ExecutionStrategy.REMOTE_EXEC,
    "standalone": ExecutionStrategy.EDITOR_CMD_PYTHON,
    "runner": ExecutionStrategy.EDITOR_CMD_PYTHON,
    "editor_cmd_python": ExecutionStrategy.EDITOR_CMD_PYTHON,
}

QUERY_SYNONYMS = {
    "健康": ("doctor", "health", "smoke", "validate", "readiness"),
    "检查": ("audit", "doctor", "validate", "check"),
    "验证": ("audit", "probe", "validate", "smoke"),
    "结构": ("architecture", "boundary", "inventory", "layout"),
    "架构": ("architecture", "boundary", "inventory", "layout"),
    "脚本": ("script", "tool", "python"),
    "跨项目": ("bundle", "install", "scaffold", "portable"),
    "安装": ("install", "bundle", "scaffold"),
    "打包": ("bundle", "package", "portable"),
    "清单": ("manifest", "catalog", "inventory"),
    "安全": ("gate", "policy", "read_only"),
    "本地": ("local", "tool"),
    "独立": ("editor_cmd_python", "standalone", "runner"),
    "无头": ("editor_cmd_python", "standalone", "runner", "commandlet"),
    "远程": ("remote_exec", "remote", "ue_python"),
}


def health_report(service, target_root=None):
    descriptor = service.descriptor()
    validation = service.validate_report().as_dict()
    boundary = service.boundary_report().as_dict()
    readiness = service.readiness_report().as_dict()
    smoke = service.smoke(target_root=target_root)
    checks = [
        _check_summary("about", descriptor.get("readiness", {}).get("ok"), descriptor.get("schema_version"), descriptor.get("readiness", {}).get("issue_count")),
        _check_summary("validate", validation.get("ok"), validation.get("schema_version"), validation.get("issue_count")),
        _check_summary("boundary", boundary.get("ok"), boundary.get("schema_version"), boundary.get("issue_count")),
        _check_summary("doctor", readiness.get("ok"), readiness.get("schema_version"), readiness.get("issue_count")),
        _check_summary("smoke", smoke.get("ok"), smoke.get("schema_version"), _failed_smoke_checks(smoke)),
    ]
    return {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "ok": all(check["ok"] for check in checks),
        "target_root": smoke.get("target_root"),
        "task_count": descriptor.get("task_count"),
        "checks": checks,
        "reports": {
            "about": descriptor,
            "validate": validation,
            "boundary": boundary,
            "doctor": readiness,
            "smoke": smoke,
        },
    }


def group_report(service, group, max_risk=None, max_mode=None):
    group_key = (group or "").lower()
    if group_key in GROUP_KIND_ALIASES:
        tasks = service.list_specs(
            kind=GROUP_KIND_ALIASES[group_key],
            max_risk=max_risk,
            max_mode=max_mode,
        )
        group_type = "kind"
    elif group_key in (ExecutionMode.LOCAL, ExecutionMode.UE_EDITOR, ExecutionMode.UE_PIE):
        tasks = [task for task in service.list_specs(max_risk=max_risk, max_mode=max_mode) if task.effective_execution_mode() == group_key]
        group_type = "execution_mode"
    elif group_key in GROUP_STRATEGY_ALIASES:
        strategy = GROUP_STRATEGY_ALIASES[group_key]
        tasks = [task for task in service.list_specs(max_risk=max_risk, max_mode=max_mode) if task.effective_execution_strategy() == strategy]
        group_type = "execution_strategy"
    elif group_key in (TaskRisk.READ_ONLY, TaskRisk.WRITES_ASSETS, TaskRisk.MIGRATION, TaskRisk.DESTRUCTIVE):
        tasks = [task for task in service.list_specs(max_risk=max_risk, max_mode=max_mode) if task.effective_risk() == group_key]
        group_type = "risk"
    else:
        tasks = service.list_specs(tag=group, max_risk=max_risk, max_mode=max_mode)
        group_type = "tag"
    return {
        "schema_version": GROUP_SCHEMA_VERSION,
        "group": group,
        "group_type": group_type,
        "task_count": len(tasks),
        "tasks": [task.as_dict() for task in tasks],
    }


def recommend_tasks(service, query, max_risk=None, max_mode=None, limit=10):
    tokens = _query_tokens(query)
    tasks = service.list_specs(max_risk=max_risk, max_mode=max_mode)
    scored = []
    for task in tasks:
        score, matches = _score_task(task, tokens)
        if score > 0 or not tokens:
            scored.append((score, task, matches))
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].effective_execution_mode(),
            item[1].effective_execution_strategy(),
            item[1].effective_risk(),
            item[1].task_id,
        )
    )
    results = []
    for score, task, matches in scored[: max(1, limit)]:
        data = task.as_dict()
        data["score"] = score
        data["matches"] = matches
        data["gate_default"] = service.gate(task.task_id)
        results.append(data)
    return {
        "schema_version": RECOMMEND_SCHEMA_VERSION,
        "query": query or "",
        "tokens": sorted(tokens),
        "task_count": len(results),
        "tasks": results,
    }


def safe_run_plan(service, task_id, max_risk=TaskRisk.READ_ONLY, max_mode=ExecutionMode.LOCAL):
    gate = service.gate(task_id, max_risk=max_risk, max_mode=max_mode)
    plan = service.plan(task_id)
    command = None
    if gate["allowed"]:
        try:
            command = service.command(task_id, max_risk=max_risk, max_mode=max_mode)
        except RuntimeError as exc:
            command = {"error": str(exc)}
    spec = service.registry.get(task_id)
    return {
        "schema_version": SAFE_RUN_SCHEMA_VERSION,
        "task_id": task_id,
        "ok": gate["allowed"],
        "execution_mode": spec.effective_execution_mode(),
        "execution_strategy": spec.effective_execution_strategy(),
        "auto_executable": gate["allowed"] and spec.effective_execution_mode() == ExecutionMode.LOCAL and spec.effective_risk() == TaskRisk.READ_ONLY,
        "gate": gate,
        "plan": plan,
        "command": command,
    }


def _check_summary(name, ok, schema_version, issue_count):
    return {
        "name": name,
        "ok": bool(ok),
        "schema_version": schema_version,
        "issue_count": issue_count or 0,
    }


def _failed_smoke_checks(smoke):
    return sum(1 for check in smoke.get("checks") or [] if not check.get("ok"))


def _query_tokens(query):
    raw = (query or "").lower().replace("_", " ").replace("-", " ")
    tokens = set(part for part in raw.split() if part)
    for key, values in QUERY_SYNONYMS.items():
        if key in (query or ""):
            tokens.update(values)
    return tokens


def _score_task(task, tokens):
    if not tokens:
        return 1, []
    haystack = {
        "task_id": task.task_id.lower(),
        "title": task.title.lower(),
        "kind": task.kind.lower(),
        "level": task.level.lower(),
        "mode": task.effective_execution_mode().lower(),
        "strategy": task.effective_execution_strategy().lower(),
        "risk": task.effective_risk().lower(),
        "description": task.description.lower(),
        "tags": " ".join(task.tags).lower(),
        "entrypoint": (task.old_entrypoint or "").lower(),
    }
    score = 0
    matches = []
    weights = {
        "task_id": 5,
        "title": 4,
        "tags": 3,
        "kind": 2,
        "mode": 2,
        "strategy": 2,
        "risk": 2,
        "description": 2,
        "entrypoint": 1,
        "level": 1,
    }
    for token in tokens:
        for field, text in haystack.items():
            if token in text:
                score += weights[field]
                matches.append({"token": token, "field": field})
                break
    return score, matches
