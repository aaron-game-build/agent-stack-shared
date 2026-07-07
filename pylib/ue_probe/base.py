"""Shared fail-fast helpers for UE editor probes and audits (editor-only).

All functions are stateless and take project-specific values (token prefixes,
Saved/ subdirectory names) as explicit parameters; each consuming project binds
its own defaults in its ``*_ops/probe_common.py`` thin layer.
"""

import importlib.util
import json
import os
import sys
import time

import unreal


def fail_with_token(token_prefix, message):
    """Print ``{token_prefix}_FAILED - {message}`` and exit 1."""
    print(f"{token_prefix}_FAILED - {message}")
    raise SystemExit(1)


def fail_probe(token_prefix, message):
    fail_with_token(token_prefix, message)


def fail_audit(token_prefix, message):
    fail_with_token(token_prefix, message)


def ensure_content_python_path():
    """Ensure Content/Python is on sys.path for Remote Execution (no __file__)."""
    root = os.path.join(unreal.Paths.project_content_dir(), "Python")
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def probes_dir():
    """Absolute path to Content/Python/probes (portable, no hardcoded drive)."""
    ensure_content_python_path()
    return os.path.join(unreal.Paths.project_content_dir(), "Python", "probes")


def run_probe_module(filename, token_prefix="PROBE"):
    """Load and execute probes/<filename> main() in the current Editor session."""
    path = os.path.join(probes_dir(), filename)
    if not os.path.isfile(path):
        fail_probe(token_prefix, f"missing probe file: {path}")
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "main"):
        fail_probe(token_prefix, f"{filename} has no main()")
    return module.main()


def saved_result_path(project_dir_name, file_name):
    return os.path.join(
        unreal.Paths.project_saved_dir(), "Automation", project_dir_name, file_name
    )


def write_result(project_dir_name, file_name, status, token="", **payload):
    path = saved_result_path(project_dir_name, file_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = {
        "status": status,
        "token": token,
        "generated_at_epoch": round(time.time(), 3),
    }
    result.update(payload)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
    return path


def class_name(obj):
    if not obj:
        return ""
    try:
        obj_class_name = obj.get_class().get_name()
        if obj_class_name == "Class" and hasattr(obj, "get_name"):
            return obj.get_name()
        return obj_class_name
    except Exception:
        return str(type(obj))


def require_class_name_contains(obj, expected, label, token_prefix):
    actual = class_name(obj)
    if expected not in actual:
        fail_probe(token_prefix, f"{label} expected {expected}, got {actual}")
    return actual


def load_class(class_path, token_prefix):
    cls = unreal.load_class(None, class_path)
    if not cls:
        fail_probe(token_prefix, f"missing class: {class_path}")
    return cls


def find_actors_by_class_path(world, class_path, token_prefix):
    cls = load_class(class_path, token_prefix)
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, cls))


def get_game_instance_subsystem(world, subsystem_class_path):
    """Return a GameInstanceSubsystem for the given world, or None.

    UE 5.7 Python often lacks GameInstance.get_subsystem and
    unreal.SubsystemBlueprintLibrary — callers must handle None. This helper
    tries both access paths before giving up.
    """
    if not world:
        return None
    game_instance = unreal.GameplayStatics.get_game_instance(world)
    if not game_instance:
        return None
    subsystem_cls = unreal.load_class(None, subsystem_class_path)
    if not subsystem_cls:
        return None

    get_subsystem = getattr(game_instance, "get_subsystem", None)
    if callable(get_subsystem):
        sub = get_subsystem(subsystem_cls)
        if sub:
            return sub

    sbl = getattr(unreal, "SubsystemBlueprintLibrary", None)
    if sbl is not None:
        get_gi_sub = getattr(sbl, "get_game_instance_subsystem", None)
        if callable(get_gi_sub):
            return get_gi_sub(game_instance, subsystem_cls)

    return None
