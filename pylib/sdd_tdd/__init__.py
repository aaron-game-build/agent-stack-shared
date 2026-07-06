"""Cross-project SDD/TDD Python helpers (no unreal dependency)."""

from .audit_runner import AuditResult, run_audit_modules
from .contract_model import (
    EVIDENCE_PROMOTION_ORDER,
    ContractClaim,
    ImpactDomain,
    ProtectedContract,
    evidence_rank,
    register_contract,
)
from .evidence_pack import EvidencePack, atomic_write_text, create_evidence_pack
from .probe_hygiene import ProbeHygieneIssue, check_probes
from .spec_schema import SpecIssue, validate_catalog

__all__ = [
    "AuditResult",
    "ContractClaim",
    "EVIDENCE_PROMOTION_ORDER",
    "EvidencePack",
    "ImpactDomain",
    "ProbeHygieneIssue",
    "ProtectedContract",
    "SpecIssue",
    "atomic_write_text",
    "check_probes",
    "create_evidence_pack",
    "evidence_rank",
    "register_contract",
    "run_audit_modules",
    "validate_catalog",
]
