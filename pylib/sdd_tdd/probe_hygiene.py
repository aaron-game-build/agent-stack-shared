"""Probe hygiene linter — project-agnostic R1-R5."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


OK_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_(?:OK|BLOCKED)\b")
MAIN_DEF_RE = re.compile(r"^def main\s*\(", re.MULTILINE)
MAIN_GUARD_RE = re.compile(r"if __name__ == ['\"]__main__['\"]")
ASSET_PATH_RE = re.compile(r"['\"](/Game/[^'\"]+)['\"]")
SCRIPT_PATH_RE = re.compile(r"['\"](/Script/[^'\"]+)['\"]")
PROBE_TARGETS_IMPORT_RE = re.compile(r"\bprobe_targets\b")


@dataclass(frozen=True)
class ProbeHygieneIssue:
    stem: str
    rule: str
    message: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_r1(stem: str) -> ProbeHygieneIssue | None:
    if stem.startswith("probe_") or stem.startswith("run_"):
        return None
    return ProbeHygieneIssue(stem, "R1", "stem must start with probe_ or run_")


def _check_r2(source: str, stem: str) -> ProbeHygieneIssue | None:
    if OK_TOKEN_RE.search(source):
        return None
    return ProbeHygieneIssue(stem, "R2", "missing stable *_OK or *_BLOCKED token")


def _check_r3(source: str, stem: str) -> ProbeHygieneIssue | None:
    if MAIN_DEF_RE.search(source) and MAIN_GUARD_RE.search(source):
        return None
    return ProbeHygieneIssue(stem, "R3", "requires def main() and if __name__ == '__main__' guard")


def _check_r4(stem: str, registered_stems: set[str] | None) -> ProbeHygieneIssue | None:
    if registered_stems is None:
        return None
    if stem in registered_stems:
        return None
    return ProbeHygieneIssue(stem, "R4", "probe stem not registered in static gate list")


def _check_r5(source: str, stem: str) -> list[ProbeHygieneIssue]:
    if PROBE_TARGETS_IMPORT_RE.search(source):
        return []
    issues: list[ProbeHygieneIssue] = []
    for pattern, label in ((ASSET_PATH_RE, "/Game/"), (SCRIPT_PATH_RE, "/Script/")):
        if pattern.search(source):
            issues.append(
                ProbeHygieneIssue(
                    stem,
                    "R5",
                    f"hardcoded {label} path without probe_targets import",
                )
            )
    return issues


def _check_orchestrator_budget(source: str, stem: str, line_budget: int) -> ProbeHygieneIssue | None:
    if not stem.startswith("run_"):
        return None
    line_count = len(source.splitlines())
    if line_count <= line_budget:
        return None
    return ProbeHygieneIssue(
        stem,
        "R3-budget",
        f"orchestrator exceeds {line_budget} lines ({line_count})",
    )


def check_probes(
    probe_dir: Path | str,
    *,
    registered_stems: set[str] | None = None,
    orchestrator_line_budget: int = 300,
) -> list[ProbeHygieneIssue]:
    """Run R1-R5 (+ orchestrator budget) on all *.py files in probe_dir."""

    directory = Path(probe_dir)
    if not directory.is_dir():
        return [ProbeHygieneIssue("", "R0", f"probe directory missing: {directory}")]

    issues: list[ProbeHygieneIssue] = []
    for path in sorted(directory.glob("*.py")):
        stem = path.stem
        source = _read(path)
        for checker in (_check_r1(stem),):
            if checker:
                issues.append(checker)
        for checker in (_check_r2(source, stem), _check_r3(source, stem), _check_r4(stem, registered_stems)):
            if checker:
                issues.append(checker)
        issues.extend(_check_r5(source, stem))
        budget_issue = _check_orchestrator_budget(source, stem, orchestrator_line_budget)
        if budget_issue:
            issues.append(budget_issue)
    return issues
