"""
Script discovery for root-wrapper based task catalogs.

This module is project-agnostic. It scans a Content/Python-style script tree and
turns compatibility root wrappers into TaskSpec records. Project registries can
then apply semantic overrides for nicer ids, success tokens, or stricter gates.
"""

import re
from dataclasses import replace
from pathlib import Path

from ue_runtime.task import ExecutionMode, TaskKind, TaskLevel, TaskRisk, TaskSpec

RUN_MODULE_RE = re.compile(
    r"run_module\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
)
DEFAULT_ALIAS_ROOTS = ("tools", "maintenance", "audits", "probes", "workflows")


def module_alias_re(extra_roots=()):
    """Regex matching legacy root-wrapper alias imports.

    ``extra_roots`` lets a project add its own ops package(s), e.g. an
    ``<project>_ops`` package, without hardcoding project names here.
    """
    roots = tuple(dict.fromkeys((*DEFAULT_ALIAS_ROOTS, *tuple(extra_roots))))
    return re.compile(
        r"from\s+(%s)\s+import\s+(\w+)\s+as\s+_impl" % "|".join(roots)
    )


MODULE_ALIAS_RE = module_alias_re()

ROOT_PREFIXES = (
    "audit",
    "diag",
    "dump",
    "fix",
    "migrate",
    "probe",
    "restore",
    "run",
    "setup",
)


def discover_root_tasks(content_python_root, repo_root=None, overrides=None, alias_roots=()):
    base = Path(content_python_root)
    root = Path(repo_root) if repo_root else base.parents[1]
    overrides = overrides or {}
    specs = []
    for path in sorted(base.glob("*.py")):
        if path.name == "__init__.py":
            continue
        spec = task_from_root_script(path, base, root, alias_roots=alias_roots)
        if not spec:
            continue
        override = overrides.get(spec.root_script or path.stem, {})
        if override:
            spec = replace(spec, **override)
        specs.append(spec)
    return specs


def task_from_root_script(path, content_python_root, repo_root, alias_roots=()):
    text = path.read_text(encoding="utf-8")
    stem = path.stem
    module = None
    root_script = stem

    match = RUN_MODULE_RE.search(text)
    if match:
        root_script, module = match.group(1), match.group(2)
    else:
        alias = module_alias_re(alias_roots).search(text)
        if alias:
            module = "%s.%s" % (alias.group(1), alias.group(2))

    if not module:
        return None

    kind, level, requires_editor, requires_pie, mutates_assets = infer_task_shape(stem, module)
    rel_path = path.relative_to(repo_root).as_posix()
    return TaskSpec(
        task_id=default_task_id(stem, kind),
        title=default_title(stem),
        kind=kind,
        level=level,
        module=module,
        root_script=root_script,
        old_entrypoint=rel_path,
        requires_editor=requires_editor,
        requires_pie=requires_pie,
        mutates_assets=mutates_assets,
        execution_mode=infer_execution_mode(requires_editor, requires_pie),
        risk=infer_risk(kind, mutates_assets),
        tags=default_tags(stem, kind, level),
        source="discovered-root-wrapper",
    )


def infer_task_shape(stem, module):
    if stem == "slice_metrics" or module.startswith("tools."):
        return TaskKind.TOOL, TaskLevel.L0, False, False, False
    if stem.startswith("audit_"):
        return TaskKind.AUDIT, TaskLevel.L3, True, False, False
    if stem.startswith("probe_"):
        return TaskKind.PROBE, TaskLevel.L4, True, True, False
    if stem.startswith("run_"):
        return TaskKind.PROBE, TaskLevel.L4, True, True, False
    if stem.startswith("setup_") or stem.startswith("final_"):
        return TaskKind.SETUP, TaskLevel.L3, True, False, True
    if stem.startswith("migrate_"):
        return TaskKind.MIGRATION, TaskLevel.L3, True, False, True
    if stem.startswith(("fix_", "restore_", "tidy_", "recompile_")):
        return TaskKind.REPAIR, TaskLevel.L3, True, False, True
    if stem.startswith(("diag_", "dump_")):
        level = TaskLevel.L4 if "pie" in stem or "asc" in stem else TaskLevel.L3
        return TaskKind.DIAGNOSTIC, level, True, level == TaskLevel.L4, False
    return TaskKind.WORKFLOW, TaskLevel.L3, True, False, False


def infer_execution_mode(requires_editor, requires_pie):
    if requires_pie:
        return ExecutionMode.UE_PIE
    if requires_editor:
        return ExecutionMode.UE_EDITOR
    return ExecutionMode.LOCAL


def infer_risk(kind, mutates_assets):
    if kind == TaskKind.MIGRATION:
        return TaskRisk.MIGRATION
    if mutates_assets:
        return TaskRisk.WRITES_ASSETS
    return TaskRisk.READ_ONLY


def default_task_id(stem, kind):
    prefix = root_prefix_for(stem)
    if prefix != "other":
        suffix = stem[len(prefix):].lstrip("_")
        return "%s.%s" % (prefix, suffix or stem)
    return "%s.%s" % (kind, stem)


def default_title(stem):
    return stem.replace("_", " ").title()


def default_tags(stem, kind, level):
    tags = [kind, level.lower()]
    prefix = root_prefix_for(stem)
    if prefix != "other":
        tags.append(prefix)
    return tuple(tags)


def root_prefix_for(stem):
    for prefix in ROOT_PREFIXES:
        if stem == prefix or stem.startswith(prefix + "_"):
            return prefix
    return "other"
