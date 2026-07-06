# Evidence Ladder (L0–L4/H)

Single semantic ladder for SDD and TDD. Labels describe **what evidence can prove**,
not prestige.

| Layer | Evidence | Proves | Does Not Prove |
|---|---|---|---|
| L0 | Source compiles / static structure exists | Code and data can load | Rules or behavior are correct |
| L1 | Unit-like checks (pure logic, schema, local scripts) | Fixed-state invariants hold | Runtime or UI clarity |
| L2 | Scenario audit / multi-step static contract | A scenario reaches expected state on paper or in logs | Player experience |
| L3 | Editor static audit / commandlet / config smoke | Project can execute the configured path in engine | Human readability or fun |
| L4 | Play-in-editor or packaged interactive pass | UI and loop are playable by a human | Audience impact |
| H | Human evidence | Observer felt the intended experience | Exhaustive correctness |

## Core Guardrails

- **Machine Green ≠ Demo Ready** — L3 green does not satisfy L4 or H.
- **L3 cannot be promoted to L4** — audits prove configuration; probes prove runtime behavior.
- **ForcedResult ≠ NaturalPlay** — diagnostic probes with immunity or forced activation do not
  substitute for natural player input (see Protected Contract evidence types).
- **Evidence completeness** — declare checked vs unchecked claims; empty log slices only prove
  negative assertions.

## Typical Mapping (UE Python Projects)

| Layer | Tooling examples |
|---|---|
| L0 | C++ build, `py_compile`, schema validators |
| L1 | `unittest` on catalog/registry; pure rule checks |
| L2 | Commandlet log validators; static demo scripts |
| L3 | `audits/*.py` in Editor (load-only, no PIE) |
| L4 | `probes/*.py` with active PIE Play |
| H | Human validation handoff + playtest notes |

## Agent REACT Alignment

- **Carry** may proceed with L0–L1 green for local edits.
- **Test** before claiming feature complete: run declared L3 for touched contracts; run L4 when
  runtime behavior changed; stop for H when claiming clarity, drama, or fun.

Project-specific Gate requirements belong in the validation lock file, not in this ladder.
