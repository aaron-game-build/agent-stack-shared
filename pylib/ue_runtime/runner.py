"""
Task execution support.

Dry-run is local and side-effect free. Real execution imports the registered task
module and calls its entry function, using the project's configured
``task_runtime.legacy_entrypoint`` module when a legacy root
script stem is available so UE module reload behavior remains consistent.
"""

import importlib

from ue_runtime.context import RuntimeContext, shell_join
from ue_runtime.task import ExecutionMode, ExecutionStrategy


class TaskRunner:
    def __init__(self, registry, context=None):
        self.registry = registry
        self.context = context

    def describe(self, task_id):
        return self.registry.get(task_id).as_dict()

    def dry_run(self, task_id):
        spec = self.registry.get(task_id)
        data = spec.as_dict()
        data["mode"] = "dry_run"
        data["runnable"] = bool(spec.module)
        data["execution_plan"] = self.execution_plan(task_id)
        if not spec.module:
            data["note"] = "metadata-only task; no Python module is registered"
        return data

    def execution_plan(self, task_id):
        spec = self.registry.get(task_id)
        mode = spec.effective_execution_mode()
        plan = {
            "task_id": spec.task_id,
            "execution_mode": mode,
            "execution_strategy": spec.effective_execution_strategy(),
            "risk": spec.effective_risk(),
            "requires_editor": spec.requires_editor,
            "requires_pie": spec.requires_pie,
            "mutates_assets": spec.mutates_assets,
            "steps": [],
        }
        strategy = spec.effective_execution_strategy()
        # Strategy overrides execution mode (e.g. editor_cmd_python can run with local mode metadata).
        if strategy == ExecutionStrategy.EDITOR_CMD_PYTHON:
            plan["steps"].append("Launch an isolated UnrealEditor-Cmd Python session instead of reusing the visible Editor.")
            if spec.requires_pie:
                plan["steps"].append("The standalone runner must load the target map and create its own PIE session.")
            else:
                plan["steps"].append("The standalone runner executes editor-side logic without depending on Remote Execution.")
        elif mode == "local":
            plan["steps"].append("Run in the current Python process via TaskRunner.run().")
        elif mode == "ue_editor":
            plan["steps"].append("Ensure Unreal Editor is open with Remote Execution enabled.")
            plan["steps"].append("Execute the legacy root entrypoint through UE Python.")
        elif mode == "ue_pie":
            plan["steps"].append("Ensure Unreal Editor is open with Remote Execution enabled.")
            plan["steps"].append("Start a real PIE Play session before running this task.")
            plan["steps"].append("Execute the legacy root entrypoint through UE Python.")
        if spec.old_entrypoint:
            entrypoint = spec.old_entrypoint.replace("\\", "/")
            plan["entrypoint"] = spec.old_entrypoint
            if self.context:
                payload = self.context.remote_exec_payload(spec)
                remote_command = self.context.remote_exec_command(spec)
                standalone_command = self.context.standalone_editor_command(spec)
                local_command = self.context.local_command(spec)
                if payload:
                    plan["recommended_remote_exec"] = payload
                if remote_command:
                    plan["recommended_remote_command"] = shell_join(remote_command)
                if standalone_command:
                    plan["recommended_standalone_command"] = shell_join(standalone_command)
                if local_command and mode == ExecutionMode.LOCAL:
                    plan["recommended_local_command"] = shell_join(local_command)
            else:
                plan["recommended_remote_exec"] = (
                    "exec(open(r'%PROJECT_ROOT%/" + entrypoint + "', encoding='utf-8').read())"
                )
        if spec.success_token:
            plan["success_token"] = spec.success_token
        return plan

    def command(self, task_id):
        spec = self.registry.get(task_id)
        if not self.context:
            raise RuntimeError("TaskRunner.command requires a RuntimeContext")
        mode = spec.effective_execution_mode()
        strategy = spec.effective_execution_strategy()
        # Strategy takes precedence over mode when selecting command transport.
        if strategy == ExecutionStrategy.EDITOR_CMD_PYTHON:
            command = self.context.standalone_editor_command(spec)
        elif mode == ExecutionMode.LOCAL:
            command = self.context.local_command(spec)
        else:
            command = self.context.remote_exec_command(spec)
        if not command:
            raise RuntimeError("Task %s has no command for mode %s strategy %s" % (task_id, mode, strategy))
        return {
            "task_id": spec.task_id,
            "execution_mode": mode,
            "execution_strategy": strategy,
            "risk": spec.effective_risk(),
            "argv": command,
            "shell": shell_join(command),
        }

    def run(self, task_id, allow_ue_process=False):
        spec = self.registry.get(task_id)
        if not spec.module:
            raise RuntimeError("Task %s has no runnable module" % task_id)
        if spec.effective_execution_mode() != ExecutionMode.LOCAL and not allow_ue_process:
            raise RuntimeError(
                "Task %s requires %s; use `plan`/`command` or pass allow_ue_process=True inside UE Python"
                % (task_id, spec.effective_execution_mode())
            )

        if spec.root_script:
            entry_module = None
            if self.context is not None:
                entry_module = self.context.task_runtime_config().get("legacy_entrypoint")
            if not entry_module:
                raise RuntimeError(
                    "Task %s uses a legacy root wrapper; set task_runtime.legacy_entrypoint "
                    "(e.g. \"<project_ops>.entrypoint\") in .ue-py-config.json" % task_id
                )
            entrypoint = importlib.import_module(entry_module)
            entrypoint = importlib.reload(entrypoint)
            return entrypoint.run_module(
                spec.root_script,
                spec.module,
                function_name=spec.function,
                reload_target=True,
            )

        module = importlib.import_module(spec.module)
        module = importlib.reload(module)
        entry = getattr(module, spec.function)
        return entry()
