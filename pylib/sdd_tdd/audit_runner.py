"""Audit module aggregator — run every audit and collect failures."""

from __future__ import annotations

import importlib
import inspect
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class AuditResult:
    module_name: str
    ok: bool
    detail: str


def _import_module(module_name: str, content_python_dir: Path | None) -> ModuleType:
    if content_python_dir is not None:
        content_python = str(content_python_dir.resolve())
        if content_python not in sys.path:
            sys.path.insert(0, content_python)
    return importlib.import_module(module_name)


def run_audit_module(module_name: str, *, content_python_dir: Path | None = None) -> AuditResult:
    try:
        module = _import_module(module_name, content_python_dir)
        importlib.reload(module)
    except Exception:
        return AuditResult(module_name, False, f"import error: {traceback.format_exc(limit=2)}")
    if not hasattr(module, "main"):
        return AuditResult(module_name, False, "no main()")
    main_fn: Callable = module.main
    try:
        signature = inspect.signature(main_fn)
        if signature.parameters:
            main_fn()
        else:
            main_fn()
        return AuditResult(module_name, True, "ok")
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 1
        return AuditResult(module_name, code == 0, f"SystemExit({code})")
    except Exception:
        return AuditResult(module_name, False, traceback.format_exc(limit=3))


def run_audit_modules(
    module_names: Sequence[str],
    *,
    content_python_dir: Path | None = None,
    ok_token: str = "RUN_AUDITS_OK",
    fail_token: str = "RUN_AUDITS_FAILED",
) -> tuple[list[AuditResult], bool]:
    results = [run_audit_module(name, content_python_dir=content_python_dir) for name in module_names]
    all_ok = all(result.ok for result in results)
    token = ok_token if all_ok else fail_token
    print(f"{token} passed={sum(1 for r in results if r.ok)}/{len(results)}")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"  [{status}] {result.module_name}: {result.detail}")
    return results, all_ok
