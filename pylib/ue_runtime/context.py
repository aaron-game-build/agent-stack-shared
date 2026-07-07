"""
Runtime context loaded from a repository root.

The context is deliberately small and JSON-backed so the runtime can be reused
by another project with only a different `.ue-py-config.json` shape or a few
constructor arguments.
"""

import json
import os
import sys
from pathlib import Path


class RuntimeContext:
    def __init__(self, repo_root, config=None):
        self.repo_root = Path(repo_root).resolve()
        self.config = config or {}

    @classmethod
    def from_repo_root(cls, repo_root):
        root = Path(repo_root).resolve()
        config_path = root / ".ue-py-config.json"
        config = {}
        if config_path.is_file():
            config = json.loads(config_path.read_text(encoding="utf-8"))
        return cls(root, config=config)

    def rel_to_abs(self, rel_path):
        return (self.repo_root / rel_path).resolve()

    def rel_to_project_slash(self, rel_path):
        return str(rel_path).replace("\\", "/")

    def ue_python_script(self):
        rel = self.config.get("ue_python_script")
        if not rel:
            return None
        return str(self.rel_to_abs(rel))

    def platform_config(self):
        platforms = self.config.get("platforms", {})
        if sys.platform == "darwin":
            return platforms.get("mac", {})
        if os.name == "nt":
            return platforms.get("windows", {})
        return platforms.get("linux", {})

    def task_registry_factory(self):
        runtime_config = self.config.get("task_runtime") or {}
        return runtime_config.get("registry_factory") or self.config.get("task_registry_factory")

    def task_runtime_config(self):
        return self.config.get("task_runtime") or {}

    def task_runtime_bootstrap_scripts(self):
        scripts = self.task_runtime_config().get("bootstrap_scripts") or []
        return [str(script) for script in scripts]

    def project_root_for_payload(self):
        current = self.platform_config()
        if current.get("project_root"):
            return current["project_root"]
        windows = (self.config.get("platforms", {}) or {}).get("windows", {})
        return windows.get("project_root") or self.repo_root.as_posix()

    def project_file_path(self):
        current = self.platform_config()
        project_root = current.get("project_root") or self.project_root_for_payload()
        project_name = self.config.get("project_name") or self.repo_root.name
        return ("%s/%s.uproject" % (project_root.rstrip("/"), project_name)).replace("\\", "/")

    def engine_root(self):
        current = self.platform_config()
        return (current.get("engine_root") or "").replace("\\", "/").rstrip("/")

    def editor_cmd_executable(self):
        engine_root = self.engine_root()
        if not engine_root:
            return None
        if os.name == "nt":
            return "%s/Binaries/Win64/UnrealEditor-Cmd.exe" % engine_root
        if sys.platform == "darwin":
            return "%s/Binaries/Mac/UnrealEditor-Cmd" % engine_root
        return "%s/Binaries/Linux/UnrealEditor-Cmd" % engine_root

    def remote_exec_payload(self, task):
        if not task.old_entrypoint:
            return None
        project_root = self.project_root_for_payload().replace("\\", "/").rstrip("/")
        entrypoint = self.rel_to_project_slash(task.old_entrypoint)
        return "exec(open(r'%s/%s', encoding='utf-8').read())" % (project_root, entrypoint)

    def remote_exec_command(self, task):
        script = self.ue_python_script()
        payload = self.remote_exec_payload(task)
        if not script or not payload:
            return None
        return [self.python_executable(), script, payload]

    def standalone_editor_command(self, task):
        entrypoint = task.effective_standalone_entrypoint()
        editor_cmd = self.editor_cmd_executable()
        if not entrypoint or not editor_cmd:
            return None
        script_path = str(self.rel_to_abs(entrypoint)).replace("\\", "/")
        return [
            editor_cmd,
            self.project_file_path(),
            "-unattended",
            "-nop4",
            "-nosplash",
            "-run=pythonscript",
            "-script=%s" % script_path,
        ]

    def local_command(self, task):
        if not task.old_entrypoint:
            return None
        return [self.python_executable(), str(self.rel_to_abs(task.old_entrypoint))]

    def python_executable(self):
        return os.environ.get("PYTHON", "python")


def shell_join(argv):
    return " ".join(_quote_arg(arg) for arg in argv)


def _quote_arg(arg):
    text = str(arg)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or '"' in text or "'" in text:
        return '"' + text.replace('"', '\\"') + '"'
    return text
