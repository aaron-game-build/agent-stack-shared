"""
Portable project scaffold for the task runtime.

The scaffold is intentionally data-only: it returns file paths and contents a
new project can copy into place, but it does not write outside the current
process. Callers can review, transform, or persist the payload themselves.
"""

import json


SCAFFOLD_SCHEMA_VERSION = "ue-task-runtime-scaffold/v1"


def build_project_scaffold(
    project_name="ExampleProject",
    registry_module="project_tasks.registry",
    bootstrap_name="task.py",
):
    project_name = _require_token(project_name, "project_name")
    registry_module = _require_module(registry_module, "registry_module")
    bootstrap_name = _require_token(bootstrap_name, "bootstrap_name")

    package_name = registry_module.rsplit(".", 1)[0] if "." in registry_module else registry_module
    package_path = "Content/Python/%s" % package_name.replace(".", "/")
    bootstrap_script = "scripts/%s" % bootstrap_name
    powershell_script = "scripts/%s.ps1" % bootstrap_name.rsplit(".", 1)[0]
    config = {
        "project_name": project_name,
        "task_runtime": {
            "registry_factory": "%s:create_registry" % registry_module,
            "bootstrap_scripts": [
                bootstrap_script,
                powershell_script,
            ],
        },
    }

    files = {
        ".ue-py-config.task-runtime.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        "%s/__init__.py" % package_path: "",
        "%s/registry.py" % package_path: _registry_template(),
        "Content/Python/tools/example_tool.py": _example_tool_template(),
        bootstrap_script: _python_bootstrap_template(),
        powershell_script: _powershell_bootstrap_template(bootstrap_name),
        "docs/task-runtime-bootstrap.md": _readme_template(
            project_name,
            registry_module,
            bootstrap_script,
            powershell_script,
        ),
    }
    return {
        "schema_version": SCAFFOLD_SCHEMA_VERSION,
        "project_name": project_name,
        "registry_factory": "%s:create_registry" % registry_module,
        "bootstrap_scripts": [
            bootstrap_script,
            powershell_script,
        ],
        "files": files,
        "next_commands": [
            "python %s about --json" % bootstrap_script,
            "python %s boundary --json" % bootstrap_script,
            "python %s validate --json" % bootstrap_script,
            "python %s doctor --json" % bootstrap_script,
            "python %s install-audit --target-root . --json" % bootstrap_script,
            "python %s smoke --target-root . --json" % bootstrap_script,
        ],
    }


def scaffold_file_names(scaffold):
    return tuple(sorted(scaffold["files"]))


def _registry_template():
    return "\n".join(
        [
            '"""Project task registry binding for ue_runtime."""',
            "",
            "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
            "",
            "",
            "def create_registry():",
            "    registry = TaskRegistry()",
            "    registry.register(TaskSpec(",
            "        task_id='tool.example',",
            "        title='Example local tool',",
            "        kind=TaskKind.TOOL,",
            "        level=TaskLevel.L0,",
            "        module='tools.example_tool',",
            "        old_entrypoint='Content/Python/tools/example_tool.py',",
            "        tags=('example',),",
            "    ))",
            "    return registry",
            "",
        ]
    )


def _example_tool_template():
    return "\n".join(
        [
            '"""Example local task for the shared task runtime scaffold."""',
            "",
            "",
            "def main():",
            "    print('TASK_RUNTIME_EXAMPLE_OK')",
            "",
            "",
            "if __name__ == '__main__':",
            "    main()",
            "",
        ]
    )


def _python_bootstrap_template():
    return "\n".join(
        [
            "#!/usr/bin/env python3",
            '"""Local bootstrap for the shared task runtime."""',
            "",
            "import sys",
            "from pathlib import Path",
            "",
            "",
            "ROOT = Path(__file__).resolve().parents[1]",
            "CONTENT_PYTHON = ROOT / 'Content' / 'Python'",
            "if str(CONTENT_PYTHON) not in sys.path:",
            "    sys.path.insert(0, str(CONTENT_PYTHON))",
            "",
            "from ue_runtime.cli import main",
            "",
            "",
            "if __name__ == '__main__':",
            "    raise SystemExit(main())",
            "",
        ]
    )


def _powershell_bootstrap_template(bootstrap_name):
    return "\n".join(
        [
            "Set-StrictMode -Version Latest",
            "$ErrorActionPreference = 'Stop'",
            "$env:PYTHONIOENCODING = 'utf-8'",
            "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path",
            "$Root = Split-Path -Parent $ScriptDir",
            "$Python = 'python'",
            "$Bootstrap = Join-Path $ScriptDir '%s'" % bootstrap_name,
            "& $Python $Bootstrap @args",
            "exit $LASTEXITCODE",
            "",
        ]
    )


def _readme_template(project_name, registry_module, bootstrap_script, powershell_script):
    return "\n".join(
        [
            "# Task Runtime Bootstrap",
            "",
            "Project: `%s`" % project_name,
            "",
            "1. Copy the scaffold files into the project root.",
            "2. Merge `.ue-py-config.task-runtime.json` into `.ue-py-config.json`.",
            "3. Keep `ue_runtime` on `Content/Python` import path.",
            "4. Register project tasks in `%s:create_registry`." % registry_module,
            "",
            "Smoke checks:",
            "",
            "```powershell",
            "python %s about --json" % bootstrap_script,
            "python %s boundary --json" % bootstrap_script,
            "python %s validate --json" % bootstrap_script,
            "python %s doctor --json" % bootstrap_script,
            "python %s install-audit --target-root . --json" % bootstrap_script,
            "python %s smoke --target-root . --json" % bootstrap_script,
            "& ./%s about --json" % powershell_script,
            "```",
            "",
        ]
    )


def _require_token(value, name):
    value = str(value or "").strip()
    if not value:
        raise ValueError("%s is required" % name)
    if any(part in value for part in ("\\", "/", "\0")):
        raise ValueError("%s must be a simple name, got %r" % (name, value))
    return value


def _require_module(value, name):
    value = str(value or "").strip()
    if not value:
        raise ValueError("%s is required" % name)
    parts = value.split(".")
    if any((not part or not part.replace("_", "a").isalnum() or part[0].isdigit()) for part in parts):
        raise ValueError("%s must be a dotted Python module path, got %r" % (name, value))
    return value
