"""
Command-line interface for the shared task runtime.
"""

import argparse
import json
import os
import subprocess
import sys

from ue_runtime.service import REGISTRY_FACTORY_ENV, REPO_ROOT_ENV, TaskService


def _print_task_table(tasks):
    if not tasks:
        print("No tasks matched.")
        return
    widths = {
        "id": max([len("id")] + [len(task.task_id) for task in tasks]),
        "kind": max([len("kind")] + [len(task.kind) for task in tasks]),
        "level": max([len("level")] + [len(task.level) for task in tasks]),
    }
    header = "%-*s  %-*s  %-*s  %s" % (
        widths["id"],
        "id",
        widths["kind"],
        "kind",
        widths["level"],
        "level",
        "title",
    )
    print(header)
    print("-" * len(header))
    for task in tasks:
        print(
            "%-*s  %-*s  %-*s  %s" % (
                widths["id"],
                task.task_id,
                widths["kind"],
                task.kind,
                widths["level"],
                task.level,
                task.title,
            )
        )


def _task_markdown(tasks, registry_factory=None):
    lines = [
        "---",
        "kb_type: module",
        "domain: ue",
        "tags:",
        "  - concept:TaskRuntime",
        "  - concept:PythonUENaming",
        "  - op:ue_task_runtime",
        "related_modules:",
        "  - ue-task-runtime.md",
        "---",
        "",
        "# Task Runtime Inventory",
        "",
        "| Task | Kind | Level | Mode | Risk | Source | Legacy entrypoint |",
        "|------|------|-------|------|------|--------|-------------------|",
    ]
    for task in tasks:
        lines.append(
            "| `%s` | %s | %s | %s | %s | %s | `%s` |"
            % (
                task.task_id,
                task.kind,
                task.level,
                task.effective_execution_mode(),
                task.effective_risk(),
                task.source,
                task.old_entrypoint or "",
            )
        )
    lines.extend(
        [
            "",
            "Generated from `%s`." % (registry_factory or "project runtime registry"),
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(description="Project task runtime")
    parser.add_argument(
        "--registry",
        help=(
            "Registry factory in module:function form. Defaults to "
            f"{REGISTRY_FACTORY_ENV}, then .ue-py-config.json task_runtime.registry_factory."
        ),
    )
    parser.add_argument(
        "--repo-root",
        help=(
            "Project root for context/config lookup. Defaults to "
            f"{REPO_ROOT_ENV}, then automatic discovery from the runtime location."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    about_parser = subparsers.add_parser("about", help="Describe runtime service protocol and project binding")
    about_parser.add_argument("--json", action="store_true", help="Emit the full service descriptor")

    list_parser = subparsers.add_parser("list", help="List registered tasks")
    list_parser.add_argument("--kind")
    list_parser.add_argument("--level")
    list_parser.add_argument("--tag")
    list_parser.add_argument("--max-risk")
    list_parser.add_argument("--max-mode")

    show_parser = subparsers.add_parser("show", help="Show one task as JSON")
    show_parser.add_argument("task_id")

    plan_parser = subparsers.add_parser("plan", help="Show the execution plan for one task")
    plan_parser.add_argument("task_id")

    command_parser = subparsers.add_parser("command", help="Show the command for one task")
    command_parser.add_argument("task_id")
    command_parser.add_argument("--max-risk")
    command_parser.add_argument("--max-mode")

    gate_parser = subparsers.add_parser("gate", help="Evaluate a task against risk/mode limits")
    gate_parser.add_argument("task_id")
    gate_parser.add_argument("--max-risk", default="read_only")
    gate_parser.add_argument("--max-mode", default="local")

    run_parser = subparsers.add_parser("run", help="Run or dry-run one task")
    run_parser.add_argument("task_id")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument(
        "--allow-ue-process",
        action="store_true",
        help="Allow importing UE tasks in the current process; intended only inside UE Python.",
    )

    docs_parser = subparsers.add_parser("docs", help="Render task inventory markdown")
    docs_parser.add_argument("--write", help="Write markdown to a file")

    manifest_parser = subparsers.add_parser("manifest", help="Render machine-readable task manifest")
    manifest_parser.add_argument("--write", help="Write JSON manifest to a file")
    manifest_parser.add_argument("--max-risk")
    manifest_parser.add_argument("--max-mode")

    subparsers.add_parser("policy", help="Show policy summary for registered tasks")

    validate_parser = subparsers.add_parser("validate", help="Validate task registry metadata")
    validate_parser.add_argument("--json", action="store_true", help="Emit a structured validation report")

    boundary_parser = subparsers.add_parser("boundary", help="Check portable runtime boundary hygiene")
    boundary_parser.add_argument("--json", action="store_true", help="Emit a structured boundary report")

    smoke_parser = subparsers.add_parser("smoke", help="Run standard installed-project smoke checks")
    smoke_parser.add_argument("--target-root", help="Target project root; defaults to the current runtime repo root")
    smoke_parser.add_argument("--json", action="store_true", help="Emit a structured smoke report")

    health_parser = subparsers.add_parser("health", help="Run the recommended Agent health check chain")
    health_parser.add_argument("--target-root", help="Target project root for smoke/install-audit checks")
    health_parser.add_argument("--json", action="store_true", help="Emit a structured health report")

    group_parser = subparsers.add_parser("group", help="List a task group by kind, execution mode, risk, or tag")
    group_parser.add_argument("group")
    group_parser.add_argument("--max-risk")
    group_parser.add_argument("--max-mode")
    group_parser.add_argument("--json", action="store_true", help="Emit a structured group report")

    recommend_parser = subparsers.add_parser("recommend", help="Recommend tasks for a goal string")
    recommend_parser.add_argument("goal", nargs="*", help="Goal/search text")
    recommend_parser.add_argument("--limit", type=int, default=10)
    recommend_parser.add_argument("--max-risk")
    recommend_parser.add_argument("--max-mode")
    recommend_parser.add_argument("--json", action="store_true", help="Emit structured recommendations")

    safe_run_parser = subparsers.add_parser("safe-run", help="Gate, plan, and optionally run a safe local task")
    safe_run_parser.add_argument("task_id")
    safe_run_parser.add_argument("--max-risk", default="read_only")
    safe_run_parser.add_argument("--max-mode", default="local")
    safe_run_parser.add_argument("--execute", action="store_true", help="Run only if the task is local and read-only")
    safe_run_parser.add_argument("--json", action="store_true", help="Emit a structured safe-run report")

    inventory_parser = subparsers.add_parser("inventory", help="Run the project script inventory helper")
    inventory_parser.add_argument("--check", action="store_true")
    inventory_parser.add_argument("--markdown", action="store_true")
    inventory_parser.add_argument("--write")
    inventory_parser.add_argument("--normalize-run-module", action="store_true")

    arch_audit_parser = subparsers.add_parser("arch-audit", help="Run the project architecture audit helper")
    arch_audit_parser.add_argument("--json", action="store_true", help="Emit structured JSON")

    adoption_check_parser = subparsers.add_parser("adoption-check", help="Run the cross-project adoption smoke helper")
    adoption_check_parser.add_argument("--output-root", default="Saved/MRRuntimeAdoptionSmoke")
    adoption_check_parser.add_argument("--project-name", default="RuntimeAdoptionSmokeProject")
    adoption_check_parser.add_argument("--registry-module", default="runtime_adoption_smoke_tasks.registry")
    adoption_check_parser.add_argument("--bootstrap-name", default="task.py")

    kb_map_parser = subparsers.add_parser("kb-map", help="Run the project script-to-KB map helper")
    kb_map_parser.add_argument("--check", action="store_true")
    kb_map_parser.add_argument("--strict", action="store_true")
    kb_map_parser.add_argument("--json", action="store_true")
    kb_map_parser.add_argument("--markdown", action="store_true")
    kb_map_parser.add_argument("--write")
    kb_map_parser.add_argument("--write-json")

    schema_parser = subparsers.add_parser("schema", help="Describe runtime JSON contracts")
    schema_parser.add_argument("name", nargs="?", default="all", help="Schema name or 'all'")

    scaffold_parser = subparsers.add_parser("scaffold", help="Render files for a new project binding")
    scaffold_parser.add_argument("--project-name", default="ExampleProject")
    scaffold_parser.add_argument("--registry-module", default="project_tasks.registry")
    scaffold_parser.add_argument("--bootstrap-name", default="task.py")
    scaffold_parser.add_argument("--json", action="store_true", help="Emit scaffold as structured JSON")
    scaffold_parser.add_argument("--file", help="Print one scaffold file by path")

    package_parser = subparsers.add_parser("package", help="Describe portable runtime package files")
    package_parser.add_argument("--json", action="store_true", help="Emit package manifest as structured JSON")

    install_plan_parser = subparsers.add_parser("install-plan", help="Render a dry-run cross-project install plan")
    install_plan_parser.add_argument("--project-name", default="ExampleProject")
    install_plan_parser.add_argument("--registry-module", default="project_tasks.registry")
    install_plan_parser.add_argument("--bootstrap-name", default="task.py")
    install_plan_parser.add_argument("--json", action="store_true", help="Emit install plan as structured JSON")

    install_audit_parser = subparsers.add_parser("install-audit", help="Audit an installed runtime copy for drift")
    install_audit_parser.add_argument("--target-root", required=True, help="Target project root")
    install_audit_parser.add_argument("--json", action="store_true", help="Emit install audit as structured JSON")

    install_parser = subparsers.add_parser("install", help="Dry-run or apply the runtime into a target project")
    install_parser.add_argument("--target-root", required=True, help="Target project root")
    install_parser.add_argument("--bundle", help="Install from a portable runtime zip bundle")
    install_parser.add_argument("--project-name", default="ExampleProject")
    install_parser.add_argument("--registry-module", default="project_tasks.registry")
    install_parser.add_argument("--bootstrap-name", default="task.py")
    install_parser.add_argument("--apply", action="store_true", help="Write files to the target project")
    install_parser.add_argument("--force", action="store_true", help="Overwrite conflicting files and config fields")
    install_parser.add_argument("--verify", action="store_true", help="Run generated smoke commands after apply")
    install_parser.add_argument("--json", action="store_true", help="Emit install result as structured JSON")

    bundle_parser = subparsers.add_parser("bundle", help="Describe or write a portable runtime zip bundle")
    bundle_parser.add_argument("--output", help="Write bundle zip to this path")
    bundle_parser.add_argument("--project-name", default="ExampleProject")
    bundle_parser.add_argument("--registry-module", default="project_tasks.registry")
    bundle_parser.add_argument("--bootstrap-name", default="task.py")
    bundle_parser.add_argument(
        "--no-scaffold",
        action="store_true",
        help="Bundle only the shared runtime package, without project scaffold files",
    )
    bundle_parser.add_argument("--json", action="store_true", help="Emit bundle manifest as structured JSON")

    bundle_verify_parser = subparsers.add_parser("bundle-verify", help="Verify a portable runtime zip bundle")
    bundle_verify_parser.add_argument("bundle", help="Bundle zip path")
    bundle_verify_parser.add_argument("--json", action="store_true", help="Emit verification report as structured JSON")

    doctor_parser = subparsers.add_parser("doctor", help="Check project readiness for runtime service integration")
    doctor_parser.add_argument("--json", action="store_true", help="Emit a structured readiness report")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    service = TaskService.from_factory(args.registry, repo_root=args.repo_root)
    registry = service.registry

    if args.command == "about":
        descriptor = service.descriptor()
        if args.json:
            print(json.dumps(descriptor, indent=2, sort_keys=True))
            return 0 if descriptor["readiness"]["ok"] else 1
        print(
            "TASK_RUNTIME_SERVICE protocol=%s tasks=%d readiness=%s registry=%s"
            % (
                descriptor["schema_version"],
                descriptor["task_count"],
                "ok" if descriptor["readiness"]["ok"] else "failed",
                descriptor["registry_factory"],
            )
        )
        return 0 if descriptor["readiness"]["ok"] else 1

    if args.command == "list":
        try:
            tasks = service.list_specs(
                kind=args.kind,
                level=args.level,
                tag=args.tag,
                max_risk=args.max_risk,
                max_mode=args.max_mode,
            )
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        _print_task_table(tasks)
        return 0

    if args.command == "show":
        print(json.dumps(service.describe(args.task_id), indent=2, sort_keys=True))
        return 0

    if args.command == "plan":
        print(json.dumps(service.plan(args.task_id), indent=2, sort_keys=True))
        return 0

    if args.command == "command":
        try:
            print(json.dumps(
                service.command(args.task_id, max_risk=args.max_risk, max_mode=args.max_mode),
                indent=2,
                sort_keys=True,
            ))
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        except RuntimeError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        return 0

    if args.command == "gate":
        try:
            gate = service.gate(args.task_id, max_risk=args.max_risk, max_mode=args.max_mode)
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        print(json.dumps(gate, indent=2, sort_keys=True))
        return 0 if gate["allowed"] else 1

    if args.command == "run":
        if args.dry_run:
            print(json.dumps(service.dry_run(args.task_id), indent=2, sort_keys=True))
            return 0
        try:
            service.run(args.task_id, allow_ue_process=args.allow_ue_process)
        except RuntimeError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        return 0

    if args.command == "docs":
        markdown = _task_markdown(registry.list(), registry_factory=service.registry_factory)
        if args.write:
            parent = os.path.dirname(os.path.abspath(args.write))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with open(args.write, "w", encoding="utf-8") as handle:
                handle.write(markdown)
            print("WROTE %s" % args.write)
            return 0
        sys.stdout.write(markdown)
        return 0

    if args.command == "manifest":
        try:
            manifest = service.manifest(max_risk=args.max_risk, max_mode=args.max_mode)
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        if args.write:
            parent = os.path.dirname(os.path.abspath(args.write))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with open(args.write, "w", encoding="utf-8") as handle:
                handle.write(text)
            print("WROTE %s" % args.write)
            return 0
        sys.stdout.write(text)
        return 0

    if args.command == "policy":
        print(json.dumps(service.policy_summary(), indent=2, sort_keys=True))
        return 0

    if args.command == "validate":
        report = service.validate_report()
        if args.json:
            print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
            return 0 if report.ok else 1
        if not report.ok:
            for issue in report.issues:
                print("ERROR: %s" % issue.message, file=sys.stderr)
            return 1
        print("TASK_REGISTRY_OK total=%d" % len(registry))
        return 0

    if args.command == "boundary":
        report = service.boundary_report()
        if args.json:
            print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
            return 0 if report.ok else 1
        if not report.ok:
            for issue in report.issues:
                print("ERROR: %s" % issue.message, file=sys.stderr)
            return 1
        print("TASK_RUNTIME_BOUNDARY_OK files=%d" % report.checked_files)
        return 0

    if args.command == "smoke":
        result = service.smoke(target_root=args.target_root)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ok"] else 1
        print(
            "TASK_RUNTIME_SMOKE status=%s target=%s checks=%d"
            % ("ok" if result["ok"] else "failed", result["target_root"], result["check_count"])
        )
        for check in result["checks"]:
            print("%s  %s  issues=%d" % ("OK" if check["ok"] else "FAIL", check["name"], check["issue_count"]))
        return 0 if result["ok"] else 1

    if args.command == "health":
        result = service.health(target_root=args.target_root)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ok"] else 1
        print(
            "TASK_RUNTIME_HEALTH status=%s target=%s tasks=%d"
            % ("ok" if result["ok"] else "failed", result["target_root"], result["task_count"])
        )
        for check in result["checks"]:
            print("%s  %s  issues=%d" % ("OK" if check["ok"] else "FAIL", check["name"], check["issue_count"]))
        return 0 if result["ok"] else 1

    if args.command == "group":
        try:
            result = service.group(args.group, max_risk=args.max_risk, max_mode=args.max_mode)
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        print("TASK_GROUP group=%s type=%s tasks=%d" % (result["group"], result["group_type"], result["task_count"]))
        _print_task_table([registry.get(task["task_id"]) for task in result["tasks"]])
        return 0

    if args.command == "recommend":
        try:
            result = service.recommend(
                " ".join(args.goal),
                max_risk=args.max_risk,
                max_mode=args.max_mode,
                limit=args.limit,
            )
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        print("TASK_RECOMMEND query=%r tasks=%d" % (result["query"], result["task_count"]))
        _print_task_table([registry.get(task["task_id"]) for task in result["tasks"]])
        return 0

    if args.command == "safe-run":
        try:
            result = service.safe_run_plan(args.task_id, max_risk=args.max_risk, max_mode=args.max_mode)
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.execute:
            if not result["auto_executable"]:
                result["execution"] = {
                    "attempted": False,
                    "ok": False,
                    "reason": "Task is not auto-executable under safe-run defaults.",
                }
            else:
                try:
                    service.run(args.task_id)
                    result["execution"] = {"attempted": True, "ok": True, "reason": ""}
                except RuntimeError as exc:
                    result["execution"] = {"attempted": True, "ok": False, "reason": str(exc)}
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            execution = result.get("execution")
            return 0 if result["ok"] and (not execution or execution["ok"]) else 1
        print(
            "TASK_SAFE_RUN task=%s allowed=%s auto=%s"
            % (args.task_id, result["gate"]["allowed"], result["auto_executable"])
        )
        if result["gate"]["reasons"]:
            for reason in result["gate"]["reasons"]:
                print("DENY %s" % reason)
        elif result["command"]:
            print(result["command"].get("shell") or result["command"].get("error"))
        execution = result.get("execution")
        if execution:
            print("execution=%s reason=%s" % ("ok" if execution["ok"] else "failed", execution["reason"]))
        return 0 if result["ok"] and (not execution or execution["ok"]) else 1

    if args.command == "inventory":
        tool_args = []
        if args.check:
            tool_args.append("--check")
        if args.markdown:
            tool_args.append("--markdown")
        if args.write:
            tool_args.extend(["--write", args.write])
        if args.normalize_run_module:
            tool_args.append("--normalize-run-module")
        return _run_project_tool(service, "Content/Python/tools/script_inventory.py", tool_args or ["--check"])

    if args.command == "arch-audit":
        return _run_project_tool(service, "Content/Python/tools/architecture_audit.py", ["--json"] if args.json else [])

    if args.command == "adoption-check":
        return _run_project_tool(
            service,
            "Content/Python/tools/runtime_adoption_smoke.py",
            [
                "--output-root",
                args.output_root,
                "--project-name",
                args.project_name,
                "--registry-module",
                args.registry_module,
                "--bootstrap-name",
                args.bootstrap_name,
            ],
        )

    if args.command == "kb-map":
        tool_args = []
        if args.check:
            tool_args.append("--check")
        if args.strict:
            tool_args.append("--strict")
        if args.json:
            tool_args.append("--json")
        if args.markdown:
            tool_args.append("--markdown")
        if args.write:
            tool_args.extend(["--write", args.write])
        if args.write_json:
            tool_args.extend(["--write-json", args.write_json])
        return _run_project_tool(service, "Content/Python/tools/script_kb_map.py", tool_args or ["--check"])

    if args.command == "schema":
        try:
            print(json.dumps(service.schema(args.name), indent=2, sort_keys=True))
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        return 0

    if args.command == "scaffold":
        try:
            scaffold = service.scaffold(
                project_name=args.project_name,
                registry_module=args.registry_module,
                bootstrap_name=args.bootstrap_name,
            )
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.file:
            files = scaffold["files"]
            if args.file not in files:
                print("ERROR: unknown scaffold file %r" % args.file, file=sys.stderr)
                return 1
            sys.stdout.write(files[args.file])
            return 0
        if args.json:
            print(json.dumps(scaffold, indent=2, sort_keys=True))
            return 0
        print("TASK_RUNTIME_SCAFFOLD project=%s files=%d" % (scaffold["project_name"], len(scaffold["files"])))
        for path in sorted(scaffold["files"]):
            print(path)
        return 0

    if args.command == "package":
        manifest = service.package_manifest()
        if args.json:
            print(json.dumps(manifest, indent=2, sort_keys=True))
            return 0
        print("TASK_RUNTIME_PACKAGE package=%s files=%d" % (manifest["package"], manifest["file_count"]))
        for file_record in manifest["files"]:
            print("%s  %s" % (file_record["sha256"], file_record["path"]))
        return 0

    if args.command == "install-plan":
        try:
            plan = service.install_plan(
                project_name=args.project_name,
                registry_module=args.registry_module,
                bootstrap_name=args.bootstrap_name,
            )
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0
        print(
            "TASK_RUNTIME_INSTALL_PLAN project=%s operations=%d"
            % (plan["project_name"], len(plan["operations"]))
        )
        for operation in plan["operations"]:
            print("%d. %s" % (operation["order"], operation["action"]))
        return 0

    if args.command == "install-audit":
        result = service.install_audit(args.target_root)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ok"] else 1
        print(
            "TASK_RUNTIME_INSTALL_AUDIT status=%s target=%s issues=%d"
            % ("ok" if result["ok"] else "drift", result["target_root"], result["issue_count"])
        )
        for issue in result["issues"]:
            print("%s  %s" % (issue["code"], issue["path"]))
        return 0 if result["ok"] else 1

    if args.command == "install":
        try:
            result = service.install(
                args.target_root,
                project_name=args.project_name,
                registry_module=args.registry_module,
                bootstrap_name=args.bootstrap_name,
                apply=args.apply,
                force=args.force,
                bundle_path=args.bundle,
                verify=args.verify,
            )
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ok"] else 1
        mode = "applied" if result["applied"] else "dry-run"
        status = "ok" if result["ok"] else "conflict"
        print(
            "TASK_RUNTIME_INSTALL mode=%s status=%s target=%s actions=%d conflicts=%d"
            % (
                mode,
                status,
                result["target_root"],
                result["action_count"],
                result["conflict_count"],
            )
        )
        for action in result["actions"]:
            print("%s  %s  %s" % (action["status"], action["kind"], action["path"]))
        post_verify = result.get("post_verify") or {}
        if post_verify.get("requested"):
            status = "ok" if post_verify.get("ok") else "failed"
            print("post_verify=%s commands=%d" % (status, post_verify.get("command_count", 0)))
        return 0 if result["ok"] else 1

    if args.command == "bundle":
        try:
            if args.output:
                result = service.bundle(
                    args.output,
                    project_name=args.project_name,
                    registry_module=args.registry_module,
                    bootstrap_name=args.bootstrap_name,
                    include_scaffold=not args.no_scaffold,
                )
            else:
                result = service.bundle_manifest(
                    project_name=args.project_name,
                    registry_module=args.registry_module,
                    bootstrap_name=args.bootstrap_name,
                    include_scaffold=not args.no_scaffold,
                )
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.output:
            print(
                "TASK_RUNTIME_BUNDLE output=%s entries=%d bytes=%d"
                % (result["output_path"], result["entry_count"], result["archive_bytes"])
            )
        else:
            print("TASK_RUNTIME_BUNDLE entries=%d" % result["entry_count"])
        for entry in result["entries"]:
            print("%s  %s" % (entry["kind"], entry["path"]))
        return 0

    if args.command == "bundle-verify":
        result = service.bundle_verify(args.bundle)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ok"] else 1
        print(
            "TASK_RUNTIME_BUNDLE_VERIFY status=%s issues=%d bundle=%s"
            % ("ok" if result["ok"] else "failed", result["issue_count"], result["bundle_path"])
        )
        for issue in result["issues"]:
            print("%s  %s" % (issue["code"], issue["message"]))
        return 0 if result["ok"] else 1

    if args.command == "doctor":
        report = service.readiness_report()
        if args.json:
            print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
            return 0 if report.ok else 1
        if report.issues:
            for issue in report.issues:
                line = "%s: %s" % (issue.severity.upper(), issue.message)
                print(line, file=sys.stderr if issue.severity == "error" else sys.stdout)
        if not report.ok:
            return 1
        print("TASK_RUNTIME_READY total=%d warnings=%d" % (report.task_count, report.warning_count))
        return 0

    raise AssertionError("Unhandled command: %s" % args.command)


def _run_project_tool(service, relative_path, tool_args):
    repo_root = service.context.repo_root if service.context else os.getcwd()
    script_path = os.path.join(str(repo_root), relative_path)
    if not os.path.isfile(script_path):
        print("ERROR: project tool not found: %s" % relative_path, file=sys.stderr)
        return 1
    completed = subprocess.run([sys.executable, script_path, *tool_args], cwd=repo_root)
    return completed.returncode
