"""Evidence pack helpers for protected contract gates."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class EvidencePack:
    evidence_root: Path
    run_id: str
    evidence_dir: Path


def validate_run_id(run_id: str) -> str:
    if not _RUN_ID_PATTERN.match(run_id):
        raise ValueError(
            "run_id must start with alphanumeric and use only letters, numbers, dot, underscore, hyphen"
        )
    return run_id


def resolve_evidence_root(
    project_root: Path,
    default_evidence_root: Path,
    evidence_root_arg: Optional[str],
) -> Path:
    project_root = project_root.resolve()
    if not evidence_root_arg:
        return default_evidence_root.resolve()
    root = Path(evidence_root_arg).expanduser()
    if not root.is_absolute():
        root = (project_root / root).resolve()
        try:
            root.relative_to(project_root)
        except ValueError as exc:
            raise ValueError("relative evidence_root must resolve under project root") from exc
    return root.resolve()


def make_default_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{os.getpid()}_{time.time_ns()}"


def create_evidence_pack(
    project_root: Path,
    default_evidence_root: Path,
    requested_run_id: Optional[str] = None,
    evidence_root_arg: Optional[str] = None,
) -> EvidencePack:
    evidence_root = resolve_evidence_root(project_root, default_evidence_root, evidence_root_arg)
    if requested_run_id:
        run_id = validate_run_id(requested_run_id)
        evidence_dir = evidence_root / run_id
        evidence_dir.mkdir(parents=True, exist_ok=False)
        return EvidencePack(evidence_root=evidence_root, run_id=run_id, evidence_dir=evidence_dir)

    for _ in range(10):
        run_id = make_default_run_id()
        evidence_dir = evidence_root / run_id
        try:
            evidence_dir.mkdir(parents=True, exist_ok=False)
            return EvidencePack(evidence_root=evidence_root, run_id=run_id, evidence_dir=evidence_dir)
        except FileExistsError:
            continue
    raise RuntimeError("failed to allocate unique evidence run_id")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
