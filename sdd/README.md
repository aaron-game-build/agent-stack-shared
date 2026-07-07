# SDD Framework (Spec-Driven Development)

Project-agnostic specification discipline for Unreal Engine game prototypes.
Canonical layer — bind per project via `AGENTS.md`, `feature_specs.py`, and
`Docs/plans/current-validation-lock.md`.

## What This Solves

- **Drift**: code, docs, and validation evidence diverge silently.
- **Overclaim**: machine-green checks mistaken for demo-ready or fun.
- **Scope creep**: features reintroduce frozen-out work as shortcuts.

SDD does not mean more documents. It means every medium+ change can answer:

```text
What is frozen?
What changed?
Which FeatureSpec owns it?
Which audit/probe/human evidence proves it?
Where does the result write back?
```

## Layout

| File | Role |
|---|---|
| [protocol.md](protocol.md) | Freeze/Delta/Spec/Production/Evidence/Archive chain |
| [evidence-ladder.md](evidence-ladder.md) | Unified L0–L4/H definitions |
| [templates/feature-slice-template.md](templates/feature-slice-template.md) | Human-facing feature slice |
| [templates/validation-lock-template.md](templates/validation-lock-template.md) | Scope freeze snapshot |

## Adoption Guide (New Project)

1. **Submodule** this repo (or copy `sdd/`, `tdd/`, and `pylib/sdd_tdd/` from it).
2. **Bind** project identity in root `AGENTS.md` and a validation lock file (e.g. `Docs/plans/current-validation-lock.md`).
3. **Create** `Content/Python/<project>_project/feature_specs.py` — catalog only, no hardcoded active lists in validators.
4. **Add** thin validators that call `spec_schema.validate_catalog()` and `probe_hygiene.check()`.
5. **Wire** validators into your static gate aggregator (Oathboard: `validate_all_static.py`).
6. **Keep** project-specific invariants in `Docs/agent-knowledge/concepts/*-sdd-governance-protocol.md` pointing here for the generic protocol.

## Relationship to TDD

SDD owns **what** must stay true and **where** proof lives.
TDD (`tdd/`) owns **how** audits, probes, and aggregation gates run.
See [../tdd/README.md](../tdd/README.md).

## Cross-Project Extraction

Submodule `agent-stack-shared` (or copy `sdd/` + `tdd/` + `pylib/sdd_tdd/` from it).
Each game repo keeps: `AGENTS.md`, validation lock, `feature_specs.py` catalog, domain probes/audits.
