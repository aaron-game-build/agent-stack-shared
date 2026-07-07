"""
Task metadata primitives for automation entrypoints.

Keep this module project-agnostic. A different Unreal project should be able to
reuse it unchanged and provide only its own task registry.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple


class TaskKind:
    AUDIT = "audit"
    DIAGNOSTIC = "diagnostic"
    MIGRATION = "migration"
    PROBE = "probe"
    REPAIR = "repair"
    SETUP = "setup"
    TOOL = "tool"
    WORKFLOW = "workflow"


class TaskLevel:
    L0 = "L0"  # local-only tooling
    L1 = "L1"  # static or metadata-only checks
    L2 = "L2"  # local Python with project files
    L3 = "L3"  # UE Editor Python
    L4 = "L4"  # PIE/runtime probe


class ExecutionMode:
    LOCAL = "local"
    UE_EDITOR = "ue_editor"
    UE_PIE = "ue_pie"


class ExecutionStrategy:
    IN_PROCESS = "in_process"
    REMOTE_EXEC = "remote_exec"
    EDITOR_CMD_PYTHON = "editor_cmd_python"


class TaskRisk:
    READ_ONLY = "read_only"
    WRITES_ASSETS = "writes_assets"
    MIGRATION = "migration"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    kind: str
    level: str
    module: Optional[str] = None
    function: str = "main"
    root_script: Optional[str] = None
    old_entrypoint: Optional[str] = None
    requires_editor: bool = False
    requires_pie: bool = False
    mutates_assets: bool = False
    success_token: Optional[str] = None
    execution_mode: Optional[str] = None
    execution_strategy: Optional[str] = None
    standalone_entrypoint: Optional[str] = None
    risk: Optional[str] = None
    tags: Tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    source: str = "manual"
    kb_refs: Tuple[str, ...] = field(default_factory=tuple)
    pitfalls: Tuple[str, ...] = field(default_factory=tuple)
    practices: Tuple[str, ...] = field(default_factory=tuple)
    required_reading: Tuple[str, ...] = field(default_factory=tuple)

    def validate(self):
        if not self.task_id:
            raise ValueError("TaskSpec.task_id is required")
        if not self.title:
            raise ValueError("TaskSpec.title is required for %s" % self.task_id)
        if not self.kind:
            raise ValueError("TaskSpec.kind is required for %s" % self.task_id)
        if not self.level:
            raise ValueError("TaskSpec.level is required for %s" % self.task_id)
        if self.requires_pie and not self.requires_editor:
            raise ValueError("%s requires PIE but does not require Editor" % self.task_id)
        if not self.module and self.function != "main":
            raise ValueError("%s has a function override but no module" % self.task_id)
        if self.execution_mode and self.execution_mode not in (
            ExecutionMode.LOCAL,
            ExecutionMode.UE_EDITOR,
            ExecutionMode.UE_PIE,
        ):
            raise ValueError("%s has unknown execution_mode: %s" % (self.task_id, self.execution_mode))
        if self.execution_strategy and self.execution_strategy not in (
            ExecutionStrategy.IN_PROCESS,
            ExecutionStrategy.REMOTE_EXEC,
            ExecutionStrategy.EDITOR_CMD_PYTHON,
        ):
            raise ValueError("%s has unknown execution_strategy: %s" % (self.task_id, self.execution_strategy))
        if self.risk and self.risk not in (
            TaskRisk.READ_ONLY,
            TaskRisk.WRITES_ASSETS,
            TaskRisk.MIGRATION,
            TaskRisk.DESTRUCTIVE,
        ):
            raise ValueError("%s has unknown risk: %s" % (self.task_id, self.risk))
        if self.requires_pie and self.effective_execution_mode() != ExecutionMode.UE_PIE:
            raise ValueError("%s requires PIE but execution_mode is not ue_pie" % self.task_id)
        if self.mutates_assets and self.effective_risk() == TaskRisk.READ_ONLY:
            raise ValueError("%s mutates assets but risk is read_only" % self.task_id)

    def effective_execution_mode(self):
        if self.execution_mode:
            return self.execution_mode
        if self.requires_pie:
            return ExecutionMode.UE_PIE
        if self.requires_editor:
            return ExecutionMode.UE_EDITOR
        return ExecutionMode.LOCAL

    def effective_risk(self):
        if self.risk:
            return self.risk
        if self.kind == TaskKind.MIGRATION:
            return TaskRisk.MIGRATION
        if self.mutates_assets:
            return TaskRisk.WRITES_ASSETS
        return TaskRisk.READ_ONLY

    def effective_execution_strategy(self):
        if self.execution_strategy:
            return self.execution_strategy
        if self.effective_execution_mode() == ExecutionMode.LOCAL:
            return ExecutionStrategy.IN_PROCESS
        standalone = self.effective_standalone_entrypoint()
        if standalone:
            stem = Path(str(standalone)).stem
            if stem.startswith("run_") and stem.endswith("_in_editor"):
                return ExecutionStrategy.EDITOR_CMD_PYTHON
        return ExecutionStrategy.REMOTE_EXEC

    def effective_standalone_entrypoint(self):
        return self.standalone_entrypoint or self.old_entrypoint

    def as_dict(self):
        return {
            "task_id": self.task_id,
            "title": self.title,
            "kind": self.kind,
            "level": self.level,
            "module": self.module,
            "function": self.function,
            "root_script": self.root_script,
            "old_entrypoint": self.old_entrypoint,
            "requires_editor": self.requires_editor,
            "requires_pie": self.requires_pie,
            "mutates_assets": self.mutates_assets,
            "success_token": self.success_token,
            "execution_mode": self.effective_execution_mode(),
            "execution_strategy": self.effective_execution_strategy(),
            "standalone_entrypoint": self.effective_standalone_entrypoint(),
            "risk": self.effective_risk(),
            "tags": list(self.tags),
            "description": self.description,
            "source": self.source,
            "kb_refs": list(self.kb_refs),
            "pitfalls": list(self.pitfalls),
            "practices": list(self.practices),
            "required_reading": list(self.required_reading),
        }
