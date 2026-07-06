"""Protected Contract meta-model — domain-neutral."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Sequence


EVIDENCE_PROMOTION_ORDER: dict[str, int] = {
    "Unclassified": 0,
    "Readiness": 1,
    "Wiring": 2,
    "Policy": 3,
    "AnimBinding": 4,
    "ForcedResult": 5,
    "PresentationScaffold": 5,
    "NaturalPlay": 6,
    "PresentationRuntime": 7,
    "HumanAccepted": 8,
}

_CONTRACTS: MutableMapping[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class ImpactDomain:
    domain_id: str
    description: str = ""


@dataclass(frozen=True)
class ContractClaim:
    claim_id: str
    requires: Sequence[str] = ()
    guarantees: Sequence[str] = ()
    impact_domains: Sequence[str] = ()
    evidence_types: Sequence[str] = ()


@dataclass(frozen=True)
class ProtectedContract:
    contract_id: str
    title: str
    claims: Sequence[ContractClaim]
    schema_version: str = "protected_contract.v1"


def evidence_rank(evidence_type: str) -> int:
    return EVIDENCE_PROMOTION_ORDER.get(evidence_type, -1)


def can_promote(from_type: str, to_type: str) -> bool:
    return evidence_rank(to_type) > evidence_rank(from_type)


def register_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    contract_id = contract.get("contract_id")
    if not contract_id:
        raise ValueError("contract missing contract_id")
    stored = deepcopy(dict(contract))
    _CONTRACTS[str(contract_id)] = stored
    return stored


def get_contract(contract_id: str) -> dict[str, Any]:
    if contract_id not in _CONTRACTS:
        raise KeyError(f"unknown contract: {contract_id}")
    return deepcopy(_CONTRACTS[contract_id])


def list_contract_ids() -> list[str]:
    return sorted(_CONTRACTS)


def clear_contracts() -> None:
    _CONTRACTS.clear()


def validate_contract_shape(contract: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if not contract.get("contract_id"):
        issues.append("missing contract_id")
    claims = contract.get("claims")
    if not isinstance(claims, list) or not claims:
        issues.append("claims must be a non-empty list")
        return issues
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            issues.append(f"claims[{index}] must be a mapping")
            continue
        if not claim.get("claim_id"):
            issues.append(f"claims[{index}] missing claim_id")
    return issues
