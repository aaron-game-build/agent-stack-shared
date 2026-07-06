"""FeatureSpec catalog validation — project-agnostic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


VALID_STATUSES = frozenset({"draft", "active", "anchored", "validated", "archived"})
REQUIRED_FIELDS = ("status", "domain_model", "contract_refs", "solution_refs", "validation")
OPTIONAL_SDD_REF_FIELDS = ("freeze_refs", "change_refs", "human_evidence_refs")
REQUIRED_LIST_FIELDS = ("domain_model", "contract_refs", "solution_refs", "validation")


@dataclass(frozen=True)
class SpecIssue:
    feature_id: str
    code: str
    message: str


def _issue(feature_id: str, code: str, message: str) -> SpecIssue:
    return SpecIssue(feature_id=feature_id, code=code, message=message)


def _require_non_empty_list(feature_id: str, field: str, value: Any, issues: list[SpecIssue]) -> None:
    if not isinstance(value, list) or not value:
        issues.append(_issue(feature_id, "missing_field", f"{field} must be a non-empty list"))
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            issues.append(_issue(feature_id, "invalid_entry", f"{field}[{index}] must be a non-empty string"))


def _validate_file_ref(
    project_root: Path,
    feature_id: str,
    section: str,
    ref: str,
    issues: list[SpecIssue],
) -> None:
    if ref.startswith("UnrealEditor") or ref.startswith("python"):
        return
    candidate = project_root / ref.replace("/", "\\") if False else project_root / Path(ref)
    if not candidate.is_file():
        issues.append(_issue(feature_id, "missing_ref", f"{section}: file not found: {ref}"))


def validate_catalog(
    catalog: Mapping[str, Mapping[str, Any]],
    project_root: Path | str,
    *,
    strict_sdd_refs: bool = False,
) -> list[SpecIssue]:
    """Validate a FeatureSpec catalog dict against the generic schema."""

    root = Path(project_root).resolve()
    issues: list[SpecIssue] = []
    seen: set[str] = set()

    for feature_id, spec in catalog.items():
        if not isinstance(spec, Mapping):
            issues.append(_issue(feature_id, "invalid_spec", "feature entry must be a mapping"))
            continue
        if feature_id in seen:
            issues.append(_issue(feature_id, "duplicate_feature_id", "duplicate feature_id"))
        seen.add(feature_id)

        for field in REQUIRED_FIELDS:
            if field not in spec:
                issues.append(_issue(feature_id, "missing_field", f"missing required field: {field}"))

        status = spec.get("status")
        if status not in VALID_STATUSES:
            issues.append(_issue(feature_id, "invalid_status", f"unknown status: {status!r}"))

        for field in REQUIRED_LIST_FIELDS:
            if field in spec:
                _require_non_empty_list(feature_id, field, spec[field], issues)

        for field in OPTIONAL_SDD_REF_FIELDS:
            if field not in spec:
                continue
            value = spec[field]
            if not isinstance(value, list):
                issues.append(_issue(feature_id, "invalid_field", f"{field} must be a list when present"))
                continue
            for index, item in enumerate(value):
                if not isinstance(item, str) or not item.strip():
                    issues.append(_issue(feature_id, "invalid_entry", f"{field}[{index}] must be a non-empty string"))

        validation = spec.get("validation", [])
        if isinstance(validation, list) and not validation:
            issues.append(_issue(feature_id, "missing_validation", "validation must not be empty"))

        for section in ("contract_refs", "solution_refs"):
            refs = spec.get(section, [])
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, str):
                        _validate_file_ref(root, feature_id, section, ref, issues)

        sdd_counts = {}
        for section in OPTIONAL_SDD_REF_FIELDS:
            refs = spec.get(section, [])
            count = len(refs) if isinstance(refs, list) else 0
            sdd_counts[section] = count
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, str):
                        _validate_file_ref(root, feature_id, section, ref, issues)

        if any(sdd_counts.values()):
            for section, count in sdd_counts.items():
                if not count:
                    issues.append(
                        _issue(
                            feature_id,
                            "incomplete_sdd_refs",
                            f"opt-in SDD evidence requires {section}",
                        )
                    )
        elif strict_sdd_refs:
            issues.append(_issue(feature_id, "missing_sdd_refs", "strict mode requires SDD ref triple"))

    return issues
