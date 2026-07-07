"""Contract tests for the project-agnostic task runtime.

These tests use an in-memory registry instead of ``mr_project`` so the runtime
facade keeps proving it can serve another project with only a different
registry binding.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

CONTENT_PYTHON = Path(__file__).resolve().parents[1]
if str(CONTENT_PYTHON) not in sys.path:
    sys.path.insert(0, str(CONTENT_PYTHON))

from ue_runtime import (  # noqa: E402
    BOUNDARY_SCHEMA_VERSION,
    BUNDLE_SCHEMA_VERSION,
    BUNDLE_VERIFY_SCHEMA_VERSION,
    DEFAULT_REGISTRY_FACTORY,
    ExecutionMode,
    GROUP_SCHEMA_VERSION,
    HEALTH_SCHEMA_VERSION,
    RECOMMEND_SCHEMA_VERSION,
    SAFE_RUN_SCHEMA_VERSION,
    INSTALL_AUDIT_SCHEMA_VERSION,
    INSTALL_RECEIPT_PATH,
    INSTALL_RECEIPT_SCHEMA_VERSION,
    INSTALL_PLAN_SCHEMA_VERSION,
    INSTALL_RESULT_SCHEMA_VERSION,
    PACKAGE_SCHEMA_VERSION,
    READINESS_SCHEMA_VERSION,
    REGISTRY_FACTORY_ENV,
    REPO_ROOT_ENV,
    RUNTIME_API_VERSION,
    RUNTIME_VERSION,
    RuntimeContext,
    SCHEMA_REGISTRY_VERSION,
    SCAFFOLD_SCHEMA_VERSION,
    SERVICE_PROTOCOL_VERSION,
    SMOKE_SCHEMA_VERSION,
    TaskKind,
    TaskLevel,
    TaskRegistry,
    TaskRisk,
    TaskService,
    TaskSpec,
    VALIDATION_SCHEMA_VERSION,
    check_runtime_boundary,
    resolve_registry_factory,
    resolve_repo_root,
)
from ue_runtime.cli import main as runtime_cli_main  # noqa: E402


class TaskRuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)
        self.context = RuntimeContext(
            self.repo_root,
            config={
                "project_name": "PortableProject",
                "ue_python_script": "Tools/ue_python.py",
                "platforms": {
                    "windows": {
                        "project_root": "X:/PortableProject",
                    },
                },
            },
        )
        self.registry = TaskRegistry()
        self.registry.register_many(
            (
                TaskSpec(
                    task_id="tool.local",
                    title="Local tool",
                    kind=TaskKind.TOOL,
                    level=TaskLevel.L0,
                    module="tools.local_tool",
                    old_entrypoint="Content/Python/tools/local_tool.py",
                    tags=("local", "portable"),
                ),
                TaskSpec(
                    task_id="setup.editor",
                    title="Editor setup",
                    kind=TaskKind.SETUP,
                    level=TaskLevel.L3,
                    module="workflows.editor_setup",
                    root_script="setup_editor",
                    old_entrypoint="Content/Python/setup_editor.py",
                    requires_editor=True,
                    mutates_assets=True,
                    tags=("editor",),
                ),
                TaskSpec(
                    task_id="probe.play",
                    title="PIE probe",
                    kind=TaskKind.PROBE,
                    level=TaskLevel.L4,
                    module="probes.play_probe",
                    root_script="probe_play",
                    old_entrypoint="Content/Python/probe_play.py",
                    requires_editor=True,
                    requires_pie=True,
                    success_token="PROBE_PLAY_OK",
                    tags=("pie",),
                ),
                TaskSpec(
                    task_id="migration.assets",
                    title="Asset migration",
                    kind=TaskKind.MIGRATION,
                    level=TaskLevel.L3,
                    module="maintenance.asset_migration",
                    old_entrypoint="Content/Python/migrate_assets.py",
                    requires_editor=True,
                    mutates_assets=True,
                    tags=("migration",),
                ),
            )
        )
        self.service = TaskService(
            self.registry,
            context=self.context,
            registry_factory="portable.registry:create_registry",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_is_stable_and_project_bound_by_context(self):
        manifest = self.service.manifest()

        self.assertEqual("ue-task-manifest/v1", manifest["schema_version"])
        self.assertEqual("PortableProject", manifest["project"]["project_name"])
        self.assertEqual("portable.registry:create_registry", manifest["registry_factory"])
        self.assertEqual(4, manifest["task_count"])
        self.assertEqual(1, manifest["summary"]["by_execution_mode"][ExecutionMode.LOCAL])
        self.assertEqual(2, manifest["summary"]["by_execution_mode"][ExecutionMode.UE_EDITOR])
        self.assertEqual(1, manifest["summary"]["by_execution_mode"][ExecutionMode.UE_PIE])

    def test_permission_scoped_catalog_filters_tasks(self):
        local = self.service.list_tasks(max_risk=TaskRisk.READ_ONLY, max_mode=ExecutionMode.LOCAL)
        editor = self.service.list_tasks(max_risk=TaskRisk.WRITES_ASSETS, max_mode=ExecutionMode.UE_EDITOR)

        self.assertEqual(["tool.local"], [task["task_id"] for task in local])
        self.assertEqual(
            ["tool.local", "setup.editor"],
            [task["task_id"] for task in editor],
        )
        self.assertEqual(1, self.service.manifest(max_risk="read_only", max_mode="local")["task_count"])

    def test_agent_facing_group_recommend_and_safe_run_reports(self):
        group = self.service.group("tool", max_risk=TaskRisk.READ_ONLY, max_mode=ExecutionMode.LOCAL)
        recommendations = self.service.recommend(
            "local portable tool",
            max_risk=TaskRisk.READ_ONLY,
            max_mode=ExecutionMode.LOCAL,
        )
        safe_run = self.service.safe_run_plan("tool.local")

        self.assertEqual(GROUP_SCHEMA_VERSION, group["schema_version"])
        self.assertEqual("tool", group["group"])
        self.assertEqual(["tool.local"], [task["task_id"] for task in group["tasks"]])
        self.assertEqual(RECOMMEND_SCHEMA_VERSION, recommendations["schema_version"])
        self.assertEqual("tool.local", recommendations["tasks"][0]["task_id"])
        self.assertGreater(recommendations["tasks"][0]["score"], 0)
        self.assertEqual(SAFE_RUN_SCHEMA_VERSION, safe_run["schema_version"])
        self.assertTrue(safe_run["auto_executable"])
        self.assertEqual("tool.local", safe_run["task_id"])
        self.assertTrue(safe_run["gate"]["allowed"])
        self.assertEqual([], safe_run["gate"]["reasons"])

    def test_command_generation_uses_context_without_importing_task_modules(self):
        local_command = self.service.command("tool.local")
        editor_command = self.service.command(
            "setup.editor",
            max_risk=TaskRisk.WRITES_ASSETS,
            max_mode=ExecutionMode.UE_EDITOR,
        )
        plan = self.service.plan("probe.play")

        self.assertEqual(ExecutionMode.LOCAL, local_command["execution_mode"])
        self.assertIn("Content", local_command["shell"])
        self.assertEqual(ExecutionMode.UE_EDITOR, editor_command["execution_mode"])
        self.assertIn("Tools", editor_command["shell"])
        self.assertIn("X:/PortableProject/Content/Python/setup_editor.py", editor_command["shell"])
        self.assertIn("recommended_remote_exec", plan)
        self.assertEqual("PROBE_PLAY_OK", plan["success_token"])

    def test_remote_payload_prefers_current_platform_project_root(self):
        context = RuntimeContext(
            self.repo_root,
            config={
                "ue_python_script": "Tools/ue_python.py",
                "platforms": {
                    "mac": {"project_root": "/Volumes/PortableProject"},
                    "windows": {"project_root": "X:/PortableProject"},
                },
            },
        )
        task = self.registry.get("setup.editor")

        payload = context.remote_exec_payload(task)

        if sys.platform == "darwin":
            self.assertIn("/Volumes/PortableProject/Content/Python/setup_editor.py", payload)
        else:
            self.assertIn("X:/PortableProject/Content/Python/setup_editor.py", payload)

    def test_policy_denial_is_explicit(self):
        gate = self.service.gate("setup.editor", max_risk=TaskRisk.READ_ONLY, max_mode=ExecutionMode.LOCAL)

        self.assertFalse(gate["allowed"])
        self.assertIn("risk writes_assets exceeds max-risk read_only", gate["reasons"])
        self.assertIn("execution_mode ue_editor exceeds max-mode local", gate["reasons"])
        with self.assertRaises(RuntimeError):
            self.service.command("setup.editor", max_risk=TaskRisk.READ_ONLY, max_mode=ExecutionMode.LOCAL)

    def test_dry_run_exposes_plan_but_does_not_execute(self):
        dry_run = self.service.dry_run("probe.play")

        self.assertEqual("dry_run", dry_run["mode"])
        self.assertTrue(dry_run["runnable"])
        self.assertEqual(ExecutionMode.UE_PIE, dry_run["execution_plan"]["execution_mode"])
        self.assertIn("Start a real PIE Play session before running this task.", dry_run["execution_plan"]["steps"])

    def test_service_validate_reports_portable_catalog_errors(self):
        source_root = self.repo_root / "Content" / "Python"
        (source_root / "tools").mkdir(parents=True)
        (source_root / "workflows").mkdir()
        (source_root / "probes").mkdir()
        (source_root / "maintenance").mkdir()
        (source_root / "tools" / "local_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        (source_root / "workflows" / "editor_setup.py").write_text("def main(): pass\n", encoding="utf-8")
        (source_root / "probes" / "play_probe.py").write_text("def main(): pass\n", encoding="utf-8")
        (source_root / "maintenance" / "asset_migration.py").write_text("def main(): pass\n", encoding="utf-8")
        for entrypoint in (
            "Content/Python/tools/local_tool.py",
            "Content/Python/setup_editor.py",
            "Content/Python/probe_play.py",
            "Content/Python/migrate_assets.py",
        ):
            path = self.repo_root / entrypoint
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pass\n", encoding="utf-8")

        self.assertEqual([], self.service.validate())

        broken = TaskRegistry()
        broken.register(
            TaskSpec(
                task_id="broken.module",
                title="Broken module",
                kind=TaskKind.TOOL,
                level=TaskLevel.L0,
                module="tools.missing_tool",
                old_entrypoint="Content/Python/missing_tool.py",
            )
        )
        broken_service = TaskService(broken, context=self.context, registry_factory="broken:create_registry")
        errors = broken_service.validate()
        report = broken_service.validate_report()

        self.assertIn("broken.module missing module file: tools.missing_tool", errors)
        self.assertIn("broken.module missing old_entrypoint: Content/Python/missing_tool.py", errors)
        self.assertFalse(report.ok)
        self.assertEqual(2, report.issue_count)
        self.assertEqual(["missing_old_entrypoint", "missing_module"], [issue.code for issue in report.issues])
        self.assertEqual(errors, report.messages())
        self.assertEqual(
            {
                "code": "missing_old_entrypoint",
                "message": "broken.module missing old_entrypoint: Content/Python/missing_tool.py",
                "severity": "error",
                "task_id": "broken.module",
            },
            report.as_dict()["issues"][0],
        )

    def test_cli_validate_json_emits_structured_report(self):
        source_root = self.repo_root / "Content" / "Python"
        tools_dir = source_root / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "cli_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        registry_module = self.repo_root / "portable_cli_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
                    "",
                    "def create_registry():",
                    "    registry = TaskRegistry()",
                    "    registry.register(TaskSpec(",
                    "        task_id='cli.tool',",
                    "        title='CLI tool',",
                    "        kind=TaskKind.TOOL,",
                    "        level=TaskLevel.L0,",
                    "        module='tools.cli_tool',",
                    "        old_entrypoint='Content/Python/tools/cli_tool.py',",
                    "    ))",
                    "    return registry",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        stdout = StringIO()
        stderr = StringIO()
        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_cli_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_cli_registry_for_test:create_registry",
                    "validate",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_cli_registry_for_test", None)

        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(
            {
                "schema_version": VALIDATION_SCHEMA_VERSION,
                "ok": True,
                "issue_count": 0,
                "issues": [],
            },
            json.loads(stdout.getvalue()),
        )

    def test_cli_validate_json_returns_issues_without_stderr_noise(self):
        registry_module = self.repo_root / "portable_cli_broken_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
                    "",
                    "def create_registry():",
                    "    registry = TaskRegistry()",
                    "    registry.register(TaskSpec(",
                    "        task_id='cli.broken',",
                    "        title='Broken CLI tool',",
                    "        kind=TaskKind.TOOL,",
                    "        level=TaskLevel.L0,",
                    "        module='tools.missing_cli_tool',",
                    "        old_entrypoint='Content/Python/missing_cli_tool.py',",
                    "    ))",
                    "    return registry",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        stdout = StringIO()
        stderr = StringIO()
        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_cli_broken_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_cli_broken_registry_for_test:create_registry",
                    "validate",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_cli_broken_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(VALIDATION_SCHEMA_VERSION, payload["schema_version"])
        self.assertFalse(payload["ok"])
        self.assertEqual(2, payload["issue_count"])
        self.assertEqual(
            ["missing_old_entrypoint", "missing_module"],
            [issue["code"] for issue in payload["issues"]],
        )

    def test_readiness_report_checks_project_service_boundary(self):
        source_root = self.repo_root / "Content" / "Python"
        tools_dir = source_root / "tools"
        scripts_dir = self.repo_root / "scripts"
        tools_dir.mkdir(parents=True)
        scripts_dir.mkdir()
        (tools_dir / "ready_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        (scripts_dir / "portable.py").write_text("pass\n", encoding="utf-8")
        entrypoint = self.repo_root / "Content" / "Python" / "tools" / "ready_tool_entry.py"
        entrypoint.write_text("pass\n", encoding="utf-8")
        (self.repo_root / ".ue-py-config.json").write_text(
            json.dumps(
                {
                    "project_name": "ReadyPortableProject",
                    "task_runtime": {
                        "registry_factory": "ready.registry:create_registry",
                        "bootstrap_scripts": ["scripts/portable.py"],
                    },
                }
            ),
            encoding="utf-8",
        )

        registry = TaskRegistry()
        registry.register(TaskSpec(
            task_id="ready.tool",
            title="Ready tool",
            kind=TaskKind.TOOL,
            level=TaskLevel.L0,
            module="tools.ready_tool",
            old_entrypoint="Content/Python/tools/ready_tool_entry.py",
        ))
        context = RuntimeContext(
            self.repo_root,
            config={
                "project_name": "ReadyPortableProject",
                "task_runtime": {
                    "registry_factory": "ready.registry:create_registry",
                    "bootstrap_scripts": ["scripts/portable.py"],
                },
            },
        )
        service = TaskService(registry, context=context, registry_factory="ready.registry:create_registry")
        report = service.readiness_report()

        self.assertTrue(report.ok)
        self.assertEqual(0, report.issue_count)
        self.assertEqual(1, report.task_count)
        self.assertEqual(READINESS_SCHEMA_VERSION, report.as_dict()["schema_version"])

    def test_readiness_report_keeps_warnings_separate_from_errors(self):
        source_root = self.repo_root / "Content" / "Python"
        tools_dir = source_root / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "warn_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        (tools_dir / "warn_tool_entry.py").write_text("pass\n", encoding="utf-8")

        registry = TaskRegistry()
        registry.register(TaskSpec(
            task_id="warn.tool",
            title="Warning tool",
            kind=TaskKind.TOOL,
            level=TaskLevel.L0,
            module="tools.warn_tool",
            old_entrypoint="Content/Python/tools/warn_tool_entry.py",
        ))
        service = TaskService(
            registry,
            context=RuntimeContext(self.repo_root),
            registry_factory="warn.registry:create_registry",
        )
        report = service.readiness_report()

        self.assertTrue(report.ok)
        self.assertEqual(0, report.error_count)
        self.assertEqual(
            ["missing_config", "implicit_registry_factory", "missing_bootstrap_scripts"],
            [issue.code for issue in report.issues],
        )

    def test_readiness_report_includes_registry_validation_errors(self):
        registry = TaskRegistry()
        registry.register(TaskSpec(
            task_id="readiness.broken",
            title="Broken readiness tool",
            kind=TaskKind.TOOL,
            level=TaskLevel.L0,
            module="tools.missing_readiness_tool",
            old_entrypoint="Content/Python/missing_readiness_tool.py",
        ))
        service = TaskService(
            registry,
            context=RuntimeContext(
                self.repo_root,
                config={
                    "task_runtime": {
                        "registry_factory": "readiness.registry:create_registry",
                        "bootstrap_scripts": ["scripts/missing.py"],
                    },
                },
            ),
            registry_factory="readiness.registry:create_registry",
        )
        report = service.readiness_report()

        self.assertFalse(report.ok)
        self.assertIn("registry_missing_module", [issue.code for issue in report.issues])
        self.assertIn("registry_missing_old_entrypoint", [issue.code for issue in report.issues])

    def test_runtime_boundary_report_passes_for_shared_runtime_package(self):
        report = self.service.boundary_report()

        self.assertTrue(report.ok)
        self.assertGreaterEqual(report.checked_files, 10)
        self.assertEqual(BOUNDARY_SCHEMA_VERSION, report.as_dict()["schema_version"])

    def test_runtime_boundary_report_rejects_project_specific_leaks(self):
        runtime_root = self.repo_root / "runtime"
        runtime_root.mkdir()
        (runtime_root / "clean.py").write_text("from ue_runtime.task import TaskSpec\n", encoding="utf-8")
        (runtime_root / "dirty_import.py").write_text("import unreal\n", encoding="utf-8")
        (runtime_root / "dirty_marker.py").write_text("PROJECT = 'MyRoguelikeGame'\n", encoding="utf-8")

        report = check_runtime_boundary(
            runtime_root,
            # Concatenated so this file passes the repo-wide forbidden-marker scan.
            forbidden_text_markers=("MyRoguelikeGame", "Oathboard", "G:/" + "UEProjects"),
        )

        self.assertFalse(report.ok)
        self.assertEqual(3, report.checked_files)
        self.assertEqual(
            ["forbidden_runtime_import", "forbidden_project_marker"],
            [issue.code for issue in report.issues],
        )

        # markers are caller-supplied: without them only the unreal ban applies
        default_report = check_runtime_boundary(runtime_root)
        self.assertEqual(
            ["forbidden_runtime_import"],
            [issue.code for issue in default_report.issues],
        )

    def test_cli_boundary_json_emits_runtime_boundary_report(self):
        registry_module = self.repo_root / "portable_boundary_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_boundary_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_boundary_registry_for_test:create_registry",
                    "boundary",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_boundary_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(BOUNDARY_SCHEMA_VERSION, payload["schema_version"])
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["checked_files"], 10)

    def test_cli_doctor_json_emits_runtime_readiness_report(self):
        source_root = self.repo_root / "Content" / "Python"
        tools_dir = source_root / "tools"
        scripts_dir = self.repo_root / "scripts"
        tools_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(exist_ok=True)
        (tools_dir / "doctor_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        (tools_dir / "doctor_tool_entry.py").write_text("pass\n", encoding="utf-8")
        (scripts_dir / "doctor.py").write_text("pass\n", encoding="utf-8")
        registry_module = self.repo_root / "portable_doctor_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
                    "",
                    "def create_registry():",
                    "    registry = TaskRegistry()",
                    "    registry.register(TaskSpec(",
                    "        task_id='doctor.tool',",
                    "        title='Doctor tool',",
                    "        kind=TaskKind.TOOL,",
                    "        level=TaskLevel.L0,",
                    "        module='tools.doctor_tool',",
                    "        old_entrypoint='Content/Python/tools/doctor_tool_entry.py',",
                    "    ))",
                    "    return registry",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.repo_root / ".ue-py-config.json").write_text(
            json.dumps(
                {
                    "project_name": "DoctorPortableProject",
                    "task_runtime": {
                        "registry_factory": "portable_doctor_registry_for_test:create_registry",
                        "bootstrap_scripts": ["scripts/doctor.py"],
                    },
                }
            ),
            encoding="utf-8",
        )

        stdout = StringIO()
        stderr = StringIO()
        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_doctor_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main(["--repo-root", str(self.repo_root), "doctor", "--json"])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_doctor_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(READINESS_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual("portable_doctor_registry_for_test:create_registry", payload["registry_factory"])

    def test_service_descriptor_exposes_protocol_and_project_binding(self):
        source_root = self.repo_root / "Content" / "Python"
        tools_dir = source_root / "tools"
        scripts_dir = self.repo_root / "scripts"
        tools_dir.mkdir(parents=True)
        scripts_dir.mkdir()
        (tools_dir / "descriptor_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        (tools_dir / "descriptor_tool_entry.py").write_text("pass\n", encoding="utf-8")
        (scripts_dir / "descriptor.py").write_text("pass\n", encoding="utf-8")
        registry = TaskRegistry()
        registry.register(TaskSpec(
            task_id="descriptor.tool",
            title="Descriptor tool",
            kind=TaskKind.TOOL,
            level=TaskLevel.L0,
            module="tools.descriptor_tool",
            old_entrypoint="Content/Python/tools/descriptor_tool_entry.py",
        ))
        service = TaskService(
            registry,
            context=RuntimeContext(
                self.repo_root,
                config={
                    "project_name": "DescriptorPortableProject",
                    "ue_python_script": "Tools/ue_python.py",
                    "task_runtime": {
                        "registry_factory": "descriptor.registry:create_registry",
                        "bootstrap_scripts": ["scripts/descriptor.py"],
                    },
                },
            ),
            registry_factory="descriptor.registry:create_registry",
        )
        descriptor = service.descriptor()

        self.assertEqual(SERVICE_PROTOCOL_VERSION, descriptor["schema_version"])
        self.assertEqual("ue-task-manifest/v1", descriptor["schemas"]["manifest"])
        self.assertEqual(BOUNDARY_SCHEMA_VERSION, descriptor["schemas"]["boundary"])
        self.assertEqual(PACKAGE_SCHEMA_VERSION, descriptor["schemas"]["package"])
        self.assertEqual(INSTALL_PLAN_SCHEMA_VERSION, descriptor["schemas"]["install_plan"])
        self.assertEqual(INSTALL_AUDIT_SCHEMA_VERSION, descriptor["schemas"]["install_audit"])
        self.assertEqual(INSTALL_RESULT_SCHEMA_VERSION, descriptor["schemas"]["install_result"])
        self.assertEqual(BUNDLE_SCHEMA_VERSION, descriptor["schemas"]["bundle"])
        self.assertEqual(BUNDLE_VERIFY_SCHEMA_VERSION, descriptor["schemas"]["bundle_verify"])
        self.assertEqual(SMOKE_SCHEMA_VERSION, descriptor["schemas"]["smoke"])
        self.assertEqual(READINESS_SCHEMA_VERSION, descriptor["schemas"]["readiness"])
        self.assertEqual(VALIDATION_SCHEMA_VERSION, descriptor["schemas"]["validation"])
        self.assertEqual(SCHEMA_REGISTRY_VERSION, descriptor["schemas"]["schema_registry"])
        self.assertEqual(SCAFFOLD_SCHEMA_VERSION, descriptor["schemas"]["scaffold"])
        self.assertEqual(HEALTH_SCHEMA_VERSION, descriptor["schemas"]["health"])
        self.assertEqual(GROUP_SCHEMA_VERSION, descriptor["schemas"]["group"])
        self.assertEqual(RECOMMEND_SCHEMA_VERSION, descriptor["schemas"]["recommend"])
        self.assertEqual(SAFE_RUN_SCHEMA_VERSION, descriptor["schemas"]["safe_run"])
        self.assertIn("task_manifest", descriptor["capabilities"])
        self.assertIn("runtime_boundary_check", descriptor["capabilities"])
        self.assertIn("runtime_package_manifest", descriptor["capabilities"])
        self.assertIn("runtime_install_plan", descriptor["capabilities"])
        self.assertIn("runtime_install_audit", descriptor["capabilities"])
        self.assertIn("runtime_smoke", descriptor["capabilities"])
        self.assertIn("runtime_installer", descriptor["capabilities"])
        self.assertIn("runtime_installer_post_verify", descriptor["capabilities"])
        self.assertIn("runtime_bundle", descriptor["capabilities"])
        self.assertIn("runtime_bundle_verify", descriptor["capabilities"])
        self.assertIn("schema_registry", descriptor["capabilities"])
        self.assertIn("project_scaffold", descriptor["capabilities"])
        self.assertIn("runtime_health", descriptor["capabilities"])
        self.assertIn("task_grouping", descriptor["capabilities"])
        self.assertIn("task_recommendations", descriptor["capabilities"])
        self.assertIn("safe_run", descriptor["capabilities"])
        self.assertIn("project_tool_wrappers", descriptor["capabilities"])
        self.assertIn("script_kb_map", descriptor["capabilities"])
        self.assertIn("about", [command["name"] for command in descriptor["commands"]])
        self.assertIn("boundary", [command["name"] for command in descriptor["commands"]])
        self.assertIn("smoke", [command["name"] for command in descriptor["commands"]])
        self.assertIn("schema", [command["name"] for command in descriptor["commands"]])
        self.assertIn("scaffold", [command["name"] for command in descriptor["commands"]])
        self.assertIn("package", [command["name"] for command in descriptor["commands"]])
        self.assertIn("install-plan", [command["name"] for command in descriptor["commands"]])
        self.assertIn("install-audit", [command["name"] for command in descriptor["commands"]])
        self.assertIn("install", [command["name"] for command in descriptor["commands"]])
        self.assertIn("bundle", [command["name"] for command in descriptor["commands"]])
        self.assertIn("bundle-verify", [command["name"] for command in descriptor["commands"]])
        self.assertIn("health", [command["name"] for command in descriptor["commands"]])
        self.assertIn("group", [command["name"] for command in descriptor["commands"]])
        self.assertIn("recommend", [command["name"] for command in descriptor["commands"]])
        self.assertIn("safe-run", [command["name"] for command in descriptor["commands"]])
        self.assertIn("inventory", [command["name"] for command in descriptor["commands"]])
        self.assertIn("arch-audit", [command["name"] for command in descriptor["commands"]])
        self.assertIn("adoption-check", [command["name"] for command in descriptor["commands"]])
        self.assertIn("kb-map", [command["name"] for command in descriptor["commands"]])
        self.assertEqual(RUNTIME_VERSION, descriptor["runtime"]["runtime_version"])
        self.assertEqual(RUNTIME_API_VERSION, descriptor["runtime"]["runtime_api"])
        self.assertEqual("ue-runtime", descriptor["runtime"]["package"])
        self.assertEqual(["scripts/descriptor.py"], descriptor["project"]["bootstrap_scripts"])
        self.assertEqual(1, descriptor["task_count"])
        self.assertTrue(descriptor["readiness"]["ok"])

    def test_schema_registry_exposes_json_contracts(self):
        all_schemas = self.service.schema()
        manifest_schema = self.service.schema("manifest")

        self.assertEqual(SCHEMA_REGISTRY_VERSION, all_schemas["schema_version"])
        self.assertIn("service", all_schemas["schemas"])
        self.assertIn("task", all_schemas["schemas"])
        self.assertIn("scaffold", all_schemas["schemas"])
        self.assertIn("package", all_schemas["schemas"])
        self.assertIn("install_plan", all_schemas["schemas"])
        self.assertIn("install_audit", all_schemas["schemas"])
        self.assertIn("install_result", all_schemas["schemas"])
        self.assertIn("bundle", all_schemas["schemas"])
        self.assertIn("bundle_verify", all_schemas["schemas"])
        self.assertIn("smoke", all_schemas["schemas"])
        self.assertEqual(SCHEMA_REGISTRY_VERSION, manifest_schema["schema_version"])
        self.assertEqual("manifest", manifest_schema["name"])
        self.assertEqual("ue-task-manifest/v1", manifest_schema["schema"]["schema_version"])
        self.assertIn("tasks", manifest_schema["schema"]["fields"])
        self.assertIn("runtime", all_schemas["schemas"]["service"]["fields"])
        self.assertIn("runtime_version", all_schemas["schemas"]["package"]["fields"])
        self.assertIn("runtime_api", all_schemas["schemas"]["package"]["fields"])
        self.assertIn("compatibility", all_schemas["schemas"]["package"]["fields"])
        self.assertIn("post_verify", all_schemas["schemas"]["install_result"]["fields"])
        self.assertIn("receipt", all_schemas["schemas"]["install_result"]["fields"])
        self.assertIn("receipt", all_schemas["schemas"]["install_audit"]["fields"])
        self.assertIn("checks", all_schemas["schemas"]["smoke"]["fields"])
        with self.assertRaises(ValueError):
            self.service.schema("missing")

    def test_cli_schema_json_emits_contract_registry(self):
        registry_module = self.repo_root / "portable_schema_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_schema_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_schema_registry_for_test:create_registry",
                    "schema",
                    "all",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_schema_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(SCHEMA_REGISTRY_VERSION, payload["schema_version"])
        self.assertIn("readiness", payload["schemas"])
        self.assertIn("boundary", payload["schemas"])
        self.assertIn("smoke", payload["schemas"])
        self.assertIn("scaffold", payload["schemas"])
        self.assertIn("install_plan", payload["schemas"])
        self.assertIn("install_audit", payload["schemas"])
        self.assertIn("install_result", payload["schemas"])
        self.assertIn("bundle", payload["schemas"])
        self.assertIn("bundle_verify", payload["schemas"])

    def test_service_package_manifest_exposes_portable_runtime_files(self):
        manifest = self.service.package_manifest()

        self.assertEqual(PACKAGE_SCHEMA_VERSION, manifest["schema_version"])
        self.assertEqual("ue-runtime", manifest["package"])
        self.assertEqual(RUNTIME_VERSION, manifest["runtime_version"])
        self.assertEqual(RUNTIME_API_VERSION, manifest["runtime_api"])
        self.assertEqual(RUNTIME_VERSION, manifest["compatibility"]["minimum_runtime_version"])
        self.assertEqual("Content/Python/ue_runtime", manifest["runtime_path"])
        self.assertGreaterEqual(manifest["file_count"], 15)
        paths = [file_record["path"] for file_record in manifest["files"]]
        self.assertIn("Content/Python/ue_runtime/service.py", paths)
        self.assertIn("Content/Python/ue_runtime/package.py", paths)
        self.assertIn("python scripts/<project_task_bootstrap>.py boundary --json", manifest["install"]["verify_commands"])
        self.assertIn("python scripts/<project_task_bootstrap>.py doctor --json", manifest["install"]["verify_commands"])
        self.assertIn(
            "python scripts/<project_task_bootstrap>.py install-audit --target-root . --json",
            manifest["install"]["verify_commands"],
        )
        self.assertIn(
            "python scripts/<project_task_bootstrap>.py smoke --target-root . --json",
            manifest["install"]["verify_commands"],
        )
        for file_record in manifest["files"]:
            self.assertRegex(file_record["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(file_record["bytes"], 0)

    def test_cli_package_json_emits_distribution_manifest(self):
        registry_module = self.repo_root / "portable_package_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_package_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_package_registry_for_test:create_registry",
                    "package",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_package_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(PACKAGE_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual("ue-runtime", payload["package"])
        self.assertEqual(RUNTIME_VERSION, payload["runtime_version"])
        self.assertEqual(RUNTIME_API_VERSION, payload["runtime_api"])
        self.assertIn(
            "Content/Python/ue_runtime/package.py",
            [file_record["path"] for file_record in payload["files"]],
        )

    def test_service_scaffold_exposes_new_project_binding_files(self):
        scaffold = self.service.scaffold(
            project_name="AnotherProject",
            registry_module="another_tasks.registry",
            bootstrap_name="tasks.py",
        )

        self.assertEqual(SCAFFOLD_SCHEMA_VERSION, scaffold["schema_version"])
        self.assertEqual("AnotherProject", scaffold["project_name"])
        self.assertEqual("another_tasks.registry:create_registry", scaffold["registry_factory"])
        self.assertEqual(["scripts/tasks.py", "scripts/tasks.ps1"], scaffold["bootstrap_scripts"])
        self.assertIn(".ue-py-config.task-runtime.json", scaffold["files"])
        self.assertIn("Content/Python/another_tasks/registry.py", scaffold["files"])
        self.assertIn("Content/Python/tools/example_tool.py", scaffold["files"])
        self.assertIn("scripts/tasks.py", scaffold["files"])
        self.assertIn("scripts/tasks.ps1", scaffold["files"])
        config = json.loads(scaffold["files"][".ue-py-config.task-runtime.json"])
        self.assertEqual("AnotherProject", config["project_name"])
        self.assertEqual(
            "another_tasks.registry:create_registry",
            config["task_runtime"]["registry_factory"],
        )
        self.assertIn("TaskRegistry", scaffold["files"]["Content/Python/another_tasks/registry.py"])
        self.assertIn("TASK_RUNTIME_EXAMPLE_OK", scaffold["files"]["Content/Python/tools/example_tool.py"])
        self.assertIn("ue_runtime.cli", scaffold["files"]["scripts/tasks.py"])
        self.assertIn("Set-StrictMode -Version Latest", scaffold["files"]["scripts/tasks.ps1"])
        self.assertIn("PYTHONIOENCODING", scaffold["files"]["scripts/tasks.ps1"])
        self.assertIn("exit $LASTEXITCODE", scaffold["files"]["scripts/tasks.ps1"])
        with self.assertRaises(ValueError):
            self.service.scaffold(project_name="Bad/Project")

    def test_service_install_plan_exposes_ordered_cross_project_operations(self):
        plan = self.service.install_plan(
            project_name="AnotherProject",
            registry_module="another_tasks.registry",
            bootstrap_name="tasks.py",
        )

        self.assertEqual(INSTALL_PLAN_SCHEMA_VERSION, plan["schema_version"])
        self.assertEqual("AnotherProject", plan["project_name"])
        self.assertEqual("another_tasks.registry:create_registry", plan["registry_factory"])
        self.assertEqual(RUNTIME_VERSION, plan["package"]["runtime_version"])
        self.assertEqual(RUNTIME_API_VERSION, plan["package"]["runtime_api"])
        self.assertGreaterEqual(plan["package"]["file_count"], 17)
        self.assertEqual(7, plan["scaffold"]["file_count"])
        self.assertEqual(
            ["copy_tree", "write_files", "merge_config", "write_receipt", "run_verify_commands"],
            [operation["action"] for operation in plan["operations"]],
        )
        self.assertIn("python scripts/tasks.py boundary --json", plan["verify_commands"])
        self.assertIn("python scripts/tasks.py doctor --json", plan["verify_commands"])
        self.assertIn("python scripts/tasks.py install-audit --target-root . --json", plan["verify_commands"])
        self.assertIn("python scripts/tasks.py smoke --target-root . --json", plan["verify_commands"])

    def test_service_install_dry_run_does_not_write_target(self):
        target = self.repo_root / "dry_target"
        result = self.service.install(
            target,
            project_name="DryProject",
            registry_module="dry_tasks.registry",
            bootstrap_name="tasks.py",
        )

        self.assertEqual(INSTALL_RESULT_SCHEMA_VERSION, result["schema_version"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["applied"])
        self.assertEqual(0, result["conflict_count"])
        self.assertFalse(result["post_verify"]["requested"])
        self.assertTrue(result["post_verify"]["skipped"])
        self.assertFalse((target / "scripts" / "tasks.py").exists())
        self.assertIn("python scripts/tasks.py doctor --json", result["verify_commands"])
        self.assertIn("python scripts/tasks.py smoke --target-root . --json", result["verify_commands"])

    def test_service_install_apply_writes_runtime_binding_and_config(self):
        target = self.repo_root / "apply_target"
        result = self.service.install(
            target,
            project_name="ApplyProject",
            registry_module="apply_tasks.registry",
            bootstrap_name="tasks.py",
            apply=True,
            verify=True,
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["dry_run"])
        self.assertTrue(result["applied"])
        self.assertTrue((target / "Content" / "Python" / "ue_runtime" / "service.py").is_file())
        self.assertTrue((target / "Content" / "Python" / "apply_tasks" / "registry.py").is_file())
        self.assertTrue((target / "scripts" / "tasks.py").is_file())
        config = json.loads((target / ".ue-py-config.json").read_text(encoding="utf-8"))
        self.assertEqual("ApplyProject", config["project_name"])
        self.assertEqual(
            "apply_tasks.registry:create_registry",
            config["task_runtime"]["registry_factory"],
        )
        self.assertEqual(["scripts/tasks.py", "scripts/tasks.ps1"], config["task_runtime"]["bootstrap_scripts"])
        self.assertTrue(result["post_verify"]["requested"])
        self.assertFalse(result["post_verify"]["skipped"])
        self.assertTrue(result["post_verify"]["ok"])
        self.assertEqual(6, result["post_verify"]["command_count"])
        self.assertEqual(INSTALL_RECEIPT_SCHEMA_VERSION, result["receipt"]["schema_version"])
        self.assertEqual("source_tree", result["receipt"]["source"])
        self.assertTrue((target / INSTALL_RECEIPT_PATH).is_file())
        self.assertEqual(0, _run_installed_bootstrap(target, "scripts/tasks.py", "validate", "--json").returncode)
        self.assertEqual(0, _run_installed_bootstrap(target, "scripts/tasks.py", "doctor", "--json").returncode)
        self.assertEqual(0, _run_installed_powershell(target, "scripts/tasks.ps1", "validate", "--json").returncode)
        audit = self.service.install_audit(target)
        self.assertEqual(INSTALL_AUDIT_SCHEMA_VERSION, audit["schema_version"])
        self.assertTrue(audit["ok"])
        self.assertTrue(audit["receipt"]["present"])
        self.assertTrue(audit["receipt"]["ok"])
        self.assertEqual(INSTALL_RECEIPT_SCHEMA_VERSION, audit["receipt"]["schema_version"])
        self.assertEqual(0, audit["issue_count"])
        installed_audit = _run_installed_bootstrap(
            target,
            "scripts/tasks.py",
            "install-audit",
            "--target-root",
            ".",
            "--json",
        )
        self.assertEqual(0, installed_audit.returncode, installed_audit.stderr or installed_audit.stdout)
        installed_payload = json.loads(installed_audit.stdout)
        self.assertTrue(installed_payload["ok"])
        self.assertTrue(installed_payload["receipt"]["ok"])
        self.assertGreater(installed_payload["summary"]["receipt_checked_files"], 0)
        self.assertEqual(0, installed_payload["summary"]["receipt_changed_files"])
        installed_smoke = _run_installed_bootstrap(
            target,
            "scripts/tasks.py",
            "smoke",
            "--target-root",
            ".",
            "--json",
        )
        self.assertEqual(0, installed_smoke.returncode, installed_smoke.stderr or installed_smoke.stdout)
        smoke_payload = json.loads(installed_smoke.stdout)
        self.assertEqual(SMOKE_SCHEMA_VERSION, smoke_payload["schema_version"])
        self.assertTrue(smoke_payload["ok"])
        self.assertEqual(
            ["about", "validate", "boundary", "doctor", "install-audit"],
            [check["name"] for check in smoke_payload["checks"]],
        )
        self.assertEqual(5, smoke_payload["check_count"])

    def test_service_install_audit_reports_runtime_drift(self):
        target = self.repo_root / "audit_target"
        self.service.install(
            target,
            project_name="AuditProject",
            registry_module="audit_tasks.registry",
            bootstrap_name="tasks.py",
            apply=True,
        )
        changed = target / "Content" / "Python" / "ue_runtime" / "service.py"
        changed.write_text(changed.read_text(encoding="utf-8") + "\n# local drift\n", encoding="utf-8")
        extra = target / "Content" / "Python" / "ue_runtime" / "local_patch.py"
        extra.write_text("LOCAL = True\n", encoding="utf-8")
        missing = target / "Content" / "Python" / "ue_runtime" / "runner.py"
        missing.unlink()

        audit = self.service.install_audit(target)

        self.assertFalse(audit["ok"])
        codes = [issue["code"] for issue in audit["issues"]]
        self.assertIn("sha256_mismatch", codes)
        self.assertIn("bytes_mismatch", codes)
        self.assertIn("extra_runtime_file", codes)
        self.assertIn("missing_file", codes)
        self.assertEqual(1, audit["summary"]["extra_files"])
        self.assertEqual(1, audit["summary"]["missing_files"])

    def test_installed_project_audit_detects_receipt_baseline_drift(self):
        target = self.repo_root / "standalone_audit_target"
        self.service.install(
            target,
            project_name="StandaloneAuditProject",
            registry_module="standalone_audit_tasks.registry",
            bootstrap_name="tasks.py",
            apply=True,
        )
        changed = target / "Content" / "Python" / "ue_runtime" / "service.py"
        changed.write_text(changed.read_text(encoding="utf-8") + "\n# installed drift\n", encoding="utf-8")

        installed_audit = _run_installed_bootstrap(
            target,
            "scripts/tasks.py",
            "install-audit",
            "--target-root",
            ".",
            "--json",
        )

        self.assertEqual(1, installed_audit.returncode)
        payload = json.loads(installed_audit.stdout)
        self.assertFalse(payload["ok"])
        codes = [issue["code"] for issue in payload["issues"]]
        self.assertIn("receipt_sha256_mismatch", codes)
        self.assertIn("receipt_bytes_mismatch", codes)
        self.assertGreaterEqual(payload["summary"]["receipt_checked_files"], 1)
        self.assertGreaterEqual(payload["summary"]["receipt_changed_files"], 1)
        installed_smoke = _run_installed_bootstrap(
            target,
            "scripts/tasks.py",
            "smoke",
            "--target-root",
            ".",
            "--json",
        )
        self.assertEqual(1, installed_smoke.returncode)
        smoke_payload = json.loads(installed_smoke.stdout)
        self.assertFalse(smoke_payload["ok"])
        self.assertFalse(smoke_payload["reports"]["install_audit"]["ok"])

    def test_service_install_reports_conflicts_without_force(self):
        target = self.repo_root / "conflict_target"
        conflict_file = target / "scripts" / "tasks.py"
        conflict_file.parent.mkdir(parents=True)
        conflict_file.write_text("different\n", encoding="utf-8")

        result = self.service.install(
            target,
            project_name="ConflictProject",
            registry_module="conflict_tasks.registry",
            bootstrap_name="tasks.py",
            apply=True,
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(1, result["conflict_count"])
        self.assertEqual("different\n", conflict_file.read_text(encoding="utf-8"))

    def test_service_bundle_manifest_describes_distributable_runtime(self):
        manifest = self.service.bundle_manifest(
            project_name="BundleProject",
            registry_module="bundle_tasks.registry",
            bootstrap_name="tasks.py",
        )

        self.assertEqual(BUNDLE_SCHEMA_VERSION, manifest["schema_version"])
        self.assertEqual("zip", manifest["archive_format"])
        self.assertEqual("BundleProject", manifest["scaffold"]["project_name"])
        self.assertEqual("bundle_tasks.registry:create_registry", manifest["scaffold"]["registry_factory"])
        self.assertEqual(RUNTIME_VERSION, manifest["package"]["runtime_version"])
        self.assertEqual(RUNTIME_API_VERSION, manifest["package"]["runtime_api"])
        self.assertGreaterEqual(manifest["package"]["file_count"], 20)
        self.assertGreaterEqual(manifest["entry_count"], 28)
        paths = [entry["path"] for entry in manifest["entries"]]
        self.assertIn("ue-runtime-bundle.json", paths)
        self.assertIn("Content/Python/ue_runtime/service.py", paths)
        self.assertIn("Content/Python/bundle_tasks/registry.py", paths)
        self.assertIn("Content/Python/tools/example_tool.py", paths)
        self.assertIn("scripts/tasks.py", paths)

    def test_service_bundle_writes_zip_with_manifest_runtime_and_scaffold(self):
        output = self.repo_root / "bundle-output" / "ue-runtime.zip"
        result = self.service.bundle(
            output,
            project_name="ZipProject",
            registry_module="zip_tasks.registry",
            bootstrap_name="tasks.py",
        )

        self.assertEqual(BUNDLE_SCHEMA_VERSION, result["schema_version"])
        self.assertTrue(output.is_file())
        self.assertRegex(result["archive_sha256"], r"^[0-9a-f]{64}$")
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn("ue-runtime-bundle.json", names)
            self.assertIn("Content/Python/ue_runtime/service.py", names)
            self.assertIn("Content/Python/zip_tasks/registry.py", names)
            self.assertIn("Content/Python/tools/example_tool.py", names)
            bundled_manifest = json.loads(archive.read("ue-runtime-bundle.json").decode("utf-8"))
        self.assertEqual(BUNDLE_SCHEMA_VERSION, bundled_manifest["schema_version"])
        self.assertEqual("zip_tasks.registry:create_registry", bundled_manifest["scaffold"]["registry_factory"])

    def test_service_bundle_verify_checks_zip_integrity(self):
        output = self.repo_root / "bundle-verify" / "ue-runtime.zip"
        self.service.bundle(
            output,
            project_name="VerifyProject",
            registry_module="verify_tasks.registry",
            bootstrap_name="tasks.py",
        )

        report = self.service.bundle_verify(output)

        self.assertEqual(BUNDLE_VERIFY_SCHEMA_VERSION, report["schema_version"])
        self.assertTrue(report["ok"])
        self.assertEqual(0, report["issue_count"])
        self.assertEqual("verify_tasks.registry:create_registry", report["manifest"]["scaffold"]["registry_factory"])
        self.assertRegex(report["archive_sha256"], r"^[0-9a-f]{64}$")

    def test_service_bundle_verify_rejects_incompatible_runtime_api(self):
        output = self.repo_root / "bundle-incompatible" / "ue-runtime.zip"
        self.service.bundle(
            output,
            project_name="IncompatibleProject",
            registry_module="incompatible_tasks.registry",
            bootstrap_name="tasks.py",
        )
        patched = self.repo_root / "bundle-incompatible" / "ue-runtime-bad-api.zip"
        with zipfile.ZipFile(output) as source, zipfile.ZipFile(patched, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "ue-runtime-bundle.json":
                    manifest = json.loads(data.decode("utf-8"))
                    manifest["package"]["runtime_api"] = "ue-task-runtime/v999"
                    data = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
                target.writestr(info, data)

        report = self.service.bundle_verify(patched)

        self.assertFalse(report["ok"])
        self.assertIn("unsupported_runtime_api", [issue["code"] for issue in report["issues"]])

    def test_service_install_can_apply_from_bundle_without_source_options(self):
        bundle = self.repo_root / "install-from-bundle" / "ue-runtime.zip"
        target = self.repo_root / "bundle_target"
        self.service.bundle(
            bundle,
            project_name="BundleInstallProject",
            registry_module="bundle_install_tasks.registry",
            bootstrap_name="tasks.py",
        )

        result = self.service.install(target, bundle_path=bundle, apply=True, verify=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        self.assertEqual("bundle", result["source"])
        self.assertTrue(result["bundle"]["ok"])
        self.assertTrue(result["post_verify"]["ok"])
        self.assertEqual(6, result["post_verify"]["command_count"])
        self.assertEqual(INSTALL_RECEIPT_SCHEMA_VERSION, result["receipt"]["schema_version"])
        self.assertEqual("bundle", result["receipt"]["source"])
        self.assertTrue((target / INSTALL_RECEIPT_PATH).is_file())
        self.assertTrue((target / "Content" / "Python" / "ue_runtime" / "service.py").is_file())
        self.assertTrue((target / "Content" / "Python" / "bundle_install_tasks" / "registry.py").is_file())
        config = json.loads((target / ".ue-py-config.json").read_text(encoding="utf-8"))
        self.assertEqual("BundleInstallProject", config["project_name"])
        self.assertEqual(
            "bundle_install_tasks.registry:create_registry",
            config["task_runtime"]["registry_factory"],
        )
        self.assertEqual(0, _run_installed_bootstrap(target, "scripts/tasks.py", "validate", "--json").returncode)
        self.assertEqual(0, _run_installed_bootstrap(target, "scripts/tasks.py", "doctor", "--json").returncode)
        self.assertEqual(0, _run_installed_powershell(target, "scripts/tasks.ps1", "doctor", "--json").returncode)

    def test_cli_scaffold_json_emits_project_binding_templates(self):
        registry_module = self.repo_root / "portable_scaffold_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_scaffold_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_scaffold_registry_for_test:create_registry",
                    "scaffold",
                    "--project-name",
                    "CliProject",
                    "--registry-module",
                    "cli_tasks.registry",
                    "--bootstrap-name",
                    "tasks.py",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_scaffold_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(SCAFFOLD_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual("CliProject", payload["project_name"])
        self.assertIn("Content/Python/cli_tasks/registry.py", payload["files"])
        self.assertIn("Content/Python/tools/example_tool.py", payload["files"])
        self.assertIn("python scripts/tasks.py boundary --json", payload["next_commands"])
        self.assertIn("python scripts/tasks.py doctor --json", payload["next_commands"])
        self.assertIn("python scripts/tasks.py install-audit --target-root . --json", payload["next_commands"])
        self.assertIn("python scripts/tasks.py smoke --target-root . --json", payload["next_commands"])

    def test_cli_install_plan_json_emits_cross_project_install_steps(self):
        registry_module = self.repo_root / "portable_install_plan_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_install_plan_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_install_plan_registry_for_test:create_registry",
                    "install-plan",
                    "--project-name",
                    "CliProject",
                    "--registry-module",
                    "cli_tasks.registry",
                    "--bootstrap-name",
                    "tasks.py",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_install_plan_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(INSTALL_PLAN_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual("CliProject", payload["project_name"])
        self.assertEqual("cli_tasks.registry:create_registry", payload["registry_factory"])
        self.assertEqual(
            ["copy_tree", "write_files", "merge_config", "write_receipt", "run_verify_commands"],
            [operation["action"] for operation in payload["operations"]],
        )
        self.assertIn("python scripts/tasks.py boundary --json", payload["verify_commands"])
        self.assertIn("python scripts/tasks.py doctor --json", payload["verify_commands"])
        self.assertIn("python scripts/tasks.py install-audit --target-root . --json", payload["verify_commands"])
        self.assertIn("python scripts/tasks.py smoke --target-root . --json", payload["verify_commands"])

    def test_cli_install_json_dry_run_emits_install_result(self):
        registry_module = self.repo_root / "portable_install_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        target = self.repo_root / "cli_install_target"
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_install_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_install_registry_for_test:create_registry",
                    "install",
                    "--target-root",
                    str(target),
                    "--project-name",
                    "CliInstallProject",
                    "--registry-module",
                    "cli_install_tasks.registry",
                    "--bootstrap-name",
                    "tasks.py",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_install_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(INSTALL_RESULT_SCHEMA_VERSION, payload["schema_version"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["ok"])
        self.assertFalse((target / "scripts" / "tasks.py").exists())

    def test_cli_install_audit_json_reports_installed_runtime_state(self):
        registry_module = self.repo_root / "portable_install_audit_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        target = self.repo_root / "cli_install_audit_target"
        self.service.install(
            target,
            project_name="CliInstallAuditProject",
            registry_module="cli_install_audit_tasks.registry",
            bootstrap_name="tasks.py",
            apply=True,
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_install_audit_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_install_audit_registry_for_test:create_registry",
                    "install-audit",
                    "--target-root",
                    str(target),
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_install_audit_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(INSTALL_AUDIT_SCHEMA_VERSION, payload["schema_version"])
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["receipt"]["present"])
        self.assertTrue(payload["receipt"]["ok"])
        self.assertEqual(0, payload["issue_count"])

    def test_cli_bundle_json_writes_portable_zip(self):
        registry_module = self.repo_root / "portable_bundle_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        output = self.repo_root / "cli-bundle" / "runtime.zip"
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_bundle_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_bundle_registry_for_test:create_registry",
                    "bundle",
                    "--output",
                    str(output),
                    "--project-name",
                    "CliBundleProject",
                    "--registry-module",
                    "cli_bundle_tasks.registry",
                    "--bootstrap-name",
                    "tasks.py",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_bundle_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(BUNDLE_SCHEMA_VERSION, payload["schema_version"])
        self.assertTrue(output.is_file())
        self.assertEqual(str(output.resolve()), payload["output_path"])

    def test_cli_bundle_verify_json_checks_portable_zip(self):
        registry_module = self.repo_root / "portable_bundle_verify_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        output = self.repo_root / "cli-bundle-verify" / "runtime.zip"
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_bundle_verify_registry_for_test", None)
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_bundle_verify_registry_for_test:create_registry",
                    "bundle",
                    "--output",
                    str(output),
                    "--project-name",
                    "CliBundleVerifyProject",
                    "--registry-module",
                    "cli_bundle_verify_tasks.registry",
                    "--bootstrap-name",
                    "tasks.py",
                    "--json",
                ])
            self.assertEqual(0, rc)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_bundle_verify_registry_for_test:create_registry",
                    "bundle-verify",
                    str(output),
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_bundle_verify_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(BUNDLE_VERIFY_SCHEMA_VERSION, payload["schema_version"])
        self.assertTrue(payload["ok"])
        self.assertEqual(0, payload["issue_count"])

    def test_cli_install_from_bundle_json_applies_bundle_payload(self):
        registry_module = self.repo_root / "portable_bundle_install_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        bundle = self.repo_root / "cli-bundle-install" / "runtime.zip"
        target = self.repo_root / "cli_bundle_install_target"
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_bundle_install_registry_for_test", None)
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_bundle_install_registry_for_test:create_registry",
                    "bundle",
                    "--output",
                    str(bundle),
                    "--project-name",
                    "CliBundleInstallProject",
                    "--registry-module",
                    "cli_bundle_install_tasks.registry",
                    "--bootstrap-name",
                    "tasks.py",
                    "--json",
                ])
            self.assertEqual(0, rc)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_bundle_install_registry_for_test:create_registry",
                    "install",
                    "--target-root",
                    str(target),
                    "--bundle",
                    str(bundle),
                    "--apply",
                    "--verify",
                    "--json",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_bundle_install_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(INSTALL_RESULT_SCHEMA_VERSION, payload["schema_version"])
        self.assertTrue(payload["applied"])
        self.assertEqual("bundle", payload["source"])
        self.assertTrue(payload["post_verify"]["ok"])
        self.assertEqual(6, payload["post_verify"]["command_count"])
        self.assertEqual(INSTALL_RECEIPT_SCHEMA_VERSION, payload["receipt"]["schema_version"])
        self.assertEqual("bundle", payload["receipt"]["source"])
        self.assertTrue((target / "Content" / "Python" / "cli_bundle_install_tasks" / "registry.py").is_file())
        self.assertEqual(0, _run_installed_bootstrap(target, "scripts/tasks.py", "validate", "--json").returncode)
        self.assertEqual(0, _run_installed_powershell(target, "scripts/tasks.ps1", "validate", "--json").returncode)

    def test_cli_scaffold_file_prints_one_template(self):
        registry_module = self.repo_root / "portable_scaffold_file_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskRegistry",
                    "",
                    "def create_registry():",
                    "    return TaskRegistry()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stdout = StringIO()
        stderr = StringIO()

        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_scaffold_file_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main([
                    "--repo-root",
                    str(self.repo_root),
                    "--registry",
                    "portable_scaffold_file_registry_for_test:create_registry",
                    "scaffold",
                    "--registry-module",
                    "file_tasks.registry",
                    "--file",
                    "Content/Python/file_tasks/registry.py",
                ])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_scaffold_file_registry_for_test", None)

        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("def create_registry():", stdout.getvalue())
        self.assertIn("TaskSpec", stdout.getvalue())

    def test_cli_about_json_emits_service_descriptor(self):
        source_root = self.repo_root / "Content" / "Python"
        tools_dir = source_root / "tools"
        scripts_dir = self.repo_root / "scripts"
        tools_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(exist_ok=True)
        (tools_dir / "about_tool.py").write_text("def main(): pass\n", encoding="utf-8")
        (tools_dir / "about_tool_entry.py").write_text("pass\n", encoding="utf-8")
        (scripts_dir / "about.py").write_text("pass\n", encoding="utf-8")
        registry_module = self.repo_root / "portable_about_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
                    "",
                    "def create_registry():",
                    "    registry = TaskRegistry()",
                    "    registry.register(TaskSpec(",
                    "        task_id='about.tool',",
                    "        title='About tool',",
                    "        kind=TaskKind.TOOL,",
                    "        level=TaskLevel.L0,",
                    "        module='tools.about_tool',",
                    "        old_entrypoint='Content/Python/tools/about_tool_entry.py',",
                    "    ))",
                    "    return registry",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.repo_root / ".ue-py-config.json").write_text(
            json.dumps(
                {
                    "project_name": "AboutPortableProject",
                    "task_runtime": {
                        "registry_factory": "portable_about_registry_for_test:create_registry",
                        "bootstrap_scripts": ["scripts/about.py"],
                    },
                }
            ),
            encoding="utf-8",
        )

        stdout = StringIO()
        stderr = StringIO()
        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_about_registry_for_test", None)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = runtime_cli_main(["--repo-root", str(self.repo_root), "about", "--json"])
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_about_registry_for_test", None)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, rc)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(SERVICE_PROTOCOL_VERSION, payload["schema_version"])
        self.assertEqual("portable_about_registry_for_test:create_registry", payload["registry_factory"])
        self.assertEqual(["scripts/about.py"], payload["project"]["bootstrap_scripts"])
        self.assertTrue(payload["readiness"]["ok"])

    def test_from_factory_uses_project_config_registry_factory(self):
        registry_module = self.repo_root / "portable_registry_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
                    "",
                    "def create_registry():",
                    "    registry = TaskRegistry()",
                    "    registry.register(TaskSpec(",
                    "        task_id='portable.tool',",
                    "        title='Portable tool',",
                    "        kind=TaskKind.TOOL,",
                    "        level=TaskLevel.L0,",
                    "        module='tools.portable_tool',",
                    "        old_entrypoint='Content/Python/tools/portable_tool.py',",
                    "    ))",
                    "    return registry",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.repo_root / ".ue-py-config.json").write_text(
            json.dumps(
                {
                    "project_name": "ConfiguredPortableProject",
                    "task_runtime": {
                        "registry_factory": "portable_registry_for_test:create_registry",
                    },
                }
            ),
            encoding="utf-8",
        )
        sys.path.insert(0, str(self.repo_root))
        try:
            sys.modules.pop("portable_registry_for_test", None)
            service = TaskService.from_factory(repo_root=self.repo_root)
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_registry_for_test", None)

        self.assertEqual("portable_registry_for_test:create_registry", service.registry_factory)
        self.assertEqual(["portable.tool"], service.registry.ids())
        self.assertEqual("ConfiguredPortableProject", service.manifest()["project"]["project_name"])

    def test_registry_factory_resolution_precedence(self):
        context = RuntimeContext(
            self.repo_root,
            config={"task_runtime": {"registry_factory": "configured:create_registry"}},
        )
        old_value = os.environ.get(REGISTRY_FACTORY_ENV)

        try:
            os.environ[REGISTRY_FACTORY_ENV] = "env:create_registry"
            self.assertEqual("explicit:create_registry", resolve_registry_factory(context, explicit="explicit:create_registry"))
            self.assertEqual("env:create_registry", resolve_registry_factory(context))
            del os.environ[REGISTRY_FACTORY_ENV]
            self.assertEqual("configured:create_registry", resolve_registry_factory(context))
            self.assertEqual(DEFAULT_REGISTRY_FACTORY, resolve_registry_factory(RuntimeContext(self.repo_root)))
        finally:
            if old_value is None:
                os.environ.pop(REGISTRY_FACTORY_ENV, None)
            else:
                os.environ[REGISTRY_FACTORY_ENV] = old_value

    def test_repo_root_resolution_precedence(self):
        explicit_root = self.repo_root / "explicit"
        env_root = self.repo_root / "env"
        old_value = os.environ.get(REPO_ROOT_ENV)

        try:
            os.environ[REPO_ROOT_ENV] = str(env_root)
            self.assertEqual(str(explicit_root), str(resolve_repo_root(explicit_root)))
            self.assertEqual(str(env_root), str(resolve_repo_root()))
        finally:
            if old_value is None:
                os.environ.pop(REPO_ROOT_ENV, None)
            else:
                os.environ[REPO_ROOT_ENV] = old_value

    def test_from_factory_can_use_repo_root_environment_variable(self):
        registry_module = self.repo_root / "portable_registry_env_for_test.py"
        registry_module.write_text(
            "\n".join(
                [
                    "from ue_runtime import TaskKind, TaskLevel, TaskRegistry, TaskSpec",
                    "",
                    "def create_registry():",
                    "    registry = TaskRegistry()",
                    "    registry.register(TaskSpec(",
                    "        task_id='env.tool',",
                    "        title='Env tool',",
                    "        kind=TaskKind.TOOL,",
                    "        level=TaskLevel.L0,",
                    "        module='tools.env_tool',",
                    "        old_entrypoint='Content/Python/tools/env_tool.py',",
                    "    ))",
                    "    return registry",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.repo_root / ".ue-py-config.json").write_text(
            json.dumps(
                {
                    "project_name": "EnvPortableProject",
                    "task_runtime": {
                        "registry_factory": "portable_registry_env_for_test:create_registry",
                    },
                }
            ),
            encoding="utf-8",
        )
        old_root = os.environ.get(REPO_ROOT_ENV)
        sys.path.insert(0, str(self.repo_root))
        try:
            os.environ[REPO_ROOT_ENV] = str(self.repo_root)
            sys.modules.pop("portable_registry_env_for_test", None)
            service = TaskService.from_factory()
        finally:
            sys.path.remove(str(self.repo_root))
            sys.modules.pop("portable_registry_env_for_test", None)
            if old_root is None:
                os.environ.pop(REPO_ROOT_ENV, None)
            else:
                os.environ[REPO_ROOT_ENV] = old_root

        self.assertEqual("portable_registry_env_for_test:create_registry", service.registry_factory)
        self.assertEqual(["env.tool"], service.registry.ids())
        self.assertEqual(self.repo_root.resolve(), service.context.repo_root)


def _run_installed_bootstrap(target_root, bootstrap_script, *args):
    return subprocess.run(
        [sys.executable, str(Path(target_root) / bootstrap_script), *args],
        cwd=target_root,
        text=True,
        capture_output=True,
    )


def _powershell_executable():
    return shutil.which("powershell") or shutil.which("pwsh")


def _run_installed_powershell(target_root, bootstrap_script, *args):
    executable = _powershell_executable()
    if not executable:
        raise unittest.SkipTest("PowerShell is not available")
    command = [executable, "-NoProfile"]
    if Path(executable).name.lower() in ("powershell", "powershell.exe"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", str(Path(target_root) / bootstrap_script), *args])
    return subprocess.run(
        command,
        cwd=target_root,
        text=True,
        capture_output=True,
    )


class LinkedConsumptionAuditTests(unittest.TestCase):
    def test_install_audit_accepts_linked_submodule_consumption(self):
        import shutil
        import tempfile

        import ue_runtime
        from ue_runtime.install_audit import audit_runtime_install

        src = Path(ue_runtime.__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            linked = Path(tmp) / "agent-stack-shared" / "pylib" / "ue_runtime"
            linked.mkdir(parents=True)
            for f in src.glob("*.py"):
                shutil.copy2(f, linked / f.name)
            report = audit_runtime_install(tmp)
            self.assertEqual("linked", report["mode"])
            self.assertTrue(report["ok"], report["issues"][:3])
            self.assertEqual(0, report["issue_count"])

    def test_install_audit_still_flags_missing_runtime(self):
        import tempfile

        from ue_runtime.install_audit import audit_runtime_install

        with tempfile.TemporaryDirectory() as tmp:
            report = audit_runtime_install(tmp)
            self.assertEqual("vendored", report["mode"])
            self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()
