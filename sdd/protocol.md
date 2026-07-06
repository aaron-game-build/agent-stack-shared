# SDD Governance Protocol (Generic)

Use this protocol for medium or larger features — anything that changes player-visible
behavior, rule contracts, validation routes, or demo-ready claims.

Skip for typo fixes, comment-only cleanup, or refactors with no behavior contract change.

## One-Line Contract

For any medium+ feature, the project must answer:

```text
What is frozen?
What changed?
Which FeatureSpec/domain model owns it?
Which audit/probe/human evidence proves it?
Where does the result write back?
```

## Artifact Chain

| Layer | Typical artifact | Role |
|---|---|---|
| Freeze | `Docs/plans/current-validation-lock.md` (or equivalent) | Confirmed / tentative / open / out-of-scope facts |
| Delta | Plan `Change Delta` section | ADDED / MODIFIED / REMOVED / UNCHANGED INVARIANTS |
| Spec | `Content/Python/<project>_project/feature_specs.py` | Machine-readable ownership and validation anchors |
| Production | `Docs/production/features/**` | Human-facing status, scenarios, playtest notes |
| Evidence | L0–L4/H | Static, contract, runtime, interactive, and human proof |
| Archive | `Docs/plans/archive/` | Old execution history after production/spec writeback |

Project paths are **binding conventions**. Replace `<project>` with your repo name.

## Freeze Baseline

| State | Meaning |
|---|---|
| Confirmed | Safe to implement against |
| Tentative | Working assumption; update before coding if contradicted |
| Open | Unresolved; do not silently decide in code |
| Out of Scope | Excluded this round; do not reintroduce as a shortcut |

## Change Delta

Use these headings in medium+ plans:

| Heading | Use |
|---|---|
| ADDED | New behavior, rule contract, evidence route, or UI explanation |
| MODIFIED | Changed behavior or validation for an existing contract |
| REMOVED | Deprecated path or no-longer-supported route |
| UNCHANGED INVARIANTS | Facts this change must not break |

## FeatureSpec Rules

- FeatureSpecs are **ownership pointers**, not design documents.
- Catalog lives in project data (`feature_specs.py`); validators live in framework (`spec_schema.py`).
- Every entry needs: `status`, `domain_model`, `contract_refs`, `solution_refs`, `validation`.
- Optional SDD lane refs (`freeze_refs`, `change_refs`, `human_evidence_refs`): if **any** is non-empty, **all three** must be present.
- Anti-pattern: only `human_evidence_refs` filled — validator reports `incomplete_sdd_refs`. Either omit all three or supply freeze + change + human together.

## Pass Questions Matrix (medium+ features)

For validation-lock Pass Questions or equivalent acceptance criteria, maintain a table mapping:

```text
question → owner feature_id → L layer → command/script → OK token → H required?
```

Gate 0 canonical example: project `Docs/production/features/gate0-pass-questions.md`.

## Human Evidence Rule

Machine evidence can prove structure and ledger changes. It cannot prove clarity, drama,
believability, or fun. Claims about player experience must name an H-level route:
playtest notes, screenshot/video review, or observer feedback.

## Writeback Rhythm

After a feature slice reaches declared evidence:

1. Update production slice status and scenarios.
2. Sync `feature_specs.py` refs if validation anchors moved.
3. Move completed plan to `Docs/plans/archive/` when production writeback exists.
4. Route escaped bugs through five-layer incident retrospective (see project KB).

## When To Enable Protected Contracts

Enable when a change touches a **core dependency** whose blast radius spans multiple
features (input grants, rule engine entry points, shared runtime facades). Use
`agent-stack/pylib/sdd_tdd/contract_model.py` + project-specific registry rows.
Do not enable before the first such dependency exists.
