"""
Small policy helpers for task risk and execution-mode gates.
"""

from ue_runtime.task import ExecutionMode, TaskRisk


RISK_ORDER = (
    TaskRisk.READ_ONLY,
    TaskRisk.WRITES_ASSETS,
    TaskRisk.MIGRATION,
    TaskRisk.DESTRUCTIVE,
)

EXECUTION_MODE_ORDER = (
    ExecutionMode.LOCAL,
    ExecutionMode.UE_EDITOR,
    ExecutionMode.UE_PIE,
)


def risk_allows(actual, maximum):
    return _rank(RISK_ORDER, actual) <= _rank(RISK_ORDER, maximum)


def mode_allows(actual, maximum):
    return _rank(EXECUTION_MODE_ORDER, actual) <= _rank(EXECUTION_MODE_ORDER, maximum)


def policy_summary(tasks):
    high_risk = [
        task.task_id for task in tasks
        if task.effective_risk() in (TaskRisk.MIGRATION, TaskRisk.DESTRUCTIVE)
    ]
    ue_required = [
        task.task_id for task in tasks
        if task.effective_execution_mode() != ExecutionMode.LOCAL
    ]
    return {
        "high_risk_task_count": len(high_risk),
        "high_risk_tasks": high_risk,
        "ue_required_task_count": len(ue_required),
        "ue_required_tasks": ue_required,
    }


def evaluate_task_policy(task, max_risk=TaskRisk.READ_ONLY, max_mode=ExecutionMode.LOCAL):
    actual_risk = task.effective_risk()
    actual_mode = task.effective_execution_mode()
    reasons = []
    if not risk_allows(actual_risk, max_risk):
        reasons.append("risk %s exceeds max-risk %s" % (actual_risk, max_risk))
    if not mode_allows(actual_mode, max_mode):
        reasons.append("execution_mode %s exceeds max-mode %s" % (actual_mode, max_mode))
    return {
        "task_id": task.task_id,
        "allowed": not reasons,
        "risk": actual_risk,
        "execution_mode": actual_mode,
        "max_risk": max_risk,
        "max_mode": max_mode,
        "reasons": reasons,
    }


def _rank(order, value):
    try:
        return order.index(value)
    except ValueError:
        raise ValueError("Unknown policy value: %s" % value)
