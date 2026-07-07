"""
Dry-run install plan for adopting the portable task runtime in another project.

The plan intentionally describes operations instead of performing them. This
keeps the runtime safe to query from tools, CI, or agents before a human or
installer decides to write files.
"""

from ue_runtime.package import build_package_manifest
from ue_runtime.scaffold import build_project_scaffold


INSTALL_PLAN_SCHEMA_VERSION = "ue-task-runtime-install-plan/v1"


def build_install_plan(
    project_name="ExampleProject",
    registry_module="project_tasks.registry",
    bootstrap_name="task.py",
):
    package = build_package_manifest()
    scaffold = build_project_scaffold(
        project_name=project_name,
        registry_module=registry_module,
        bootstrap_name=bootstrap_name,
    )
    operations = [
        {
            "order": 1,
            "action": "copy_tree",
            "source": package["runtime_path"],
            "target": package["runtime_path"],
            "file_count": package["file_count"],
            "verification": "match package.files sha256",
        },
        {
            "order": 2,
            "action": "write_files",
            "files": sorted(scaffold["files"]),
            "file_count": len(scaffold["files"]),
            "verification": "file contents equal scaffold.files values",
        },
        {
            "order": 3,
            "action": "merge_config",
            "source": ".ue-py-config.task-runtime.json",
            "target": ".ue-py-config.json",
            "fields": [
                "project_name",
                "task_runtime.registry_factory",
                "task_runtime.bootstrap_scripts",
            ],
            "verification": "doctor --json returns ok",
        },
        {
            "order": 4,
            "action": "write_receipt",
            "target": ".ue-task-runtime-install.json",
            "verification": "install-audit --json reports receipt ok after apply",
        },
        {
            "order": 5,
            "action": "run_verify_commands",
            "commands": list(scaffold["next_commands"]),
            "verification": "all commands exit 0",
        },
    ]
    return {
        "schema_version": INSTALL_PLAN_SCHEMA_VERSION,
        "project_name": scaffold["project_name"],
        "registry_factory": scaffold["registry_factory"],
        "package": {
            "schema_version": package["schema_version"],
            "package": package["package"],
            "runtime_version": package["runtime_version"],
            "runtime_api": package["runtime_api"],
            "compatibility": dict(package["compatibility"]),
            "runtime_path": package["runtime_path"],
            "file_count": package["file_count"],
        },
        "scaffold": {
            "schema_version": scaffold["schema_version"],
            "bootstrap_scripts": list(scaffold["bootstrap_scripts"]),
            "file_count": len(scaffold["files"]),
            "files": sorted(scaffold["files"]),
        },
        "operations": operations,
        "verify_commands": list(scaffold["next_commands"]),
    }
