# agent-stack-shared

A standalone repository of domain-neutral agent rules, shared across UE projects (currently
Oathboard and MyRoguelikeGame) and across tools (Claude Code, Cursor, Codex). This is a local
seed only — no remote has been created yet, and this directory is not a git repo yet.

## What belongs in the shared layer vs. the project layer

**Shared layer (this repo, `rules/*.md`)**: rules whose structure and intent are the same across
projects, once domain-specific nouns (parser/ledger/board vs. GAS/DrawDebug/ARPG spine, etc.) are
factored out into placeholders. A rule belongs here if two projects independently converged on
the same rule with only wording/example differences (see the drift report that motivated this:
`Docs/agent-knowledge/fable/stack-drift-report.md` in Oathboard), or if a rule that exists in only
one project turns out to encode a genuinely cross-project concern (e.g. multi-agent concurrency,
delegation/cost discipline, Chinese-doc encoding safety).

**Project layer (stays in each project's own repo)**:
- `AGENTS.md` — the cross-agent binding/identity layer.
- Project-specific rules with no shared analog (e.g. MR's `ue-visual-debug-gate`,
  `mr-ui-localization`, `roguelike-learning`; Oathboard's Gate 0 specifics).
- `Docs/agent-knowledge/` (or `docs/ue-agent-knowledge/` on MR) — the actual KB detail content
  that shared rules link out to via `{{KB_ROOT}}`.
- The local `agent-stack/manifest.json` — project name, repo path, KB root, and all
  `params`/`slots`/`optional` values that fill in this repo's placeholders (see
  `MANIFEST-SCHEMA.md`).

Skills and commands (`agent-stack/skills/*/SKILL.md`, `agent-stack/commands/*.md`) are **not**
covered by this seed. The two projects' skill/command sets have not yet had a drift pass; that is
future work once this rules-only v1 is validated.

## Placeholder mechanism (v1)

- `{{KEY}}` — single-value param, inline substitution.
- `{{SLOT:KEY}}` — multi-line slot substitution.
- `<!-- BEGIN OPTIONAL:KEY --> ... <!-- END OPTIONAL:KEY -->` — optional block, removed entirely
  if the project doesn't supply `KEY`.

Full key-by-key semantics and current Oathboard/MR values: `MANIFEST-SCHEMA.md`.

## Sync workflow: `--pull` / `--push`

A unified `scripts/check_stack.py` (not yet added to this seed) is intended to live in this repo,
with each consuming project calling it via a thin wrapper:

- **`--pull`**: read `rules/*.md` from this shared repo, render placeholders using the
  project's local `agent-stack/manifest.json` `shared` node, write the rendered output into the
  project's `agent-stack/rules/`, then trigger the project's existing `--sync` to regenerate
  Cursor/Codex/Claude adapters. Rendered files get a header:
  `<!-- GENERATED from agent-stack-shared; edit there, not here -->`. Any leftover `{{` after
  rendering is a hard error.
- **`--push`** (v1, deliberately conservative): **does not** auto-write back to this shared repo.
  It diffs the project's local rules against the last-pulled rendering baseline and prints a
  report of "these local edits look like they belong in shared file X" — a human then manually
  edits the shared rule here. No automatic reverse-rendering in v1.

Once a project adopts `--pull`, its local `agent-stack/rules/` stops being hand-edited canonical
content — the Drift Rule in that project's `CLAUDE.md`/`AGENTS.md` needs a one-line update to say
so.

## Integration status

| Project | Canonical rules location today | Status |
|---|---|---|
| Oathboard | `agent-stack/rules/*.md` (hand-edited) | **Pending integration** — this seed includes `oathboard-manifest-shared-draft.json` as the concrete `shared` node draft; next step is running `--pull` against it, confirming `--check` and the static gates stay green, then committing the switch to generated rules. |
| MyRoguelikeGame | `.cursor/rules/*.mdc` (hand-edited) | **Pending migration** — MR's canonical source today is `.cursor/rules/`, not `agent-stack/`. Adopting the shared layer requires a one-time structural migration inside the MR repo (move to an `agent-stack/`-shaped layout, add its own manifest `shared` node) before `--pull` can target it. This is out of scope for the current (read-only) MR access and needs separate authorization to modify the MR repo. |

## Design decisions already locked (see Oathboard's `stack-merge-proposal.md` for full rationale)

- D1: Oathboard does not get a `codegraph-indexing` detail doc; it stays on the inline codegraph
  rule (the `CODEGRAPH_DETAIL_DOC` optional block stays unconfigured for Oathboard, configured
  for MR).
- D2: Example/domain differences are resolved via placeholder substitution (params/slots), not a
  skeleton+appendix split.
- D3: Protected Contract is a shared optional block, not a fork; Oathboard doesn't configure it
  yet but the mechanism is available once it names a protected-contract list.
- D4: `agent-doc-safety`, `agent-concurrency`, and `agent-delegation-cost` (merged from MR's
  `ue-agent-delegation` + `ue-agent-cost-discipline`) all move to the shared layer.
  `ue-visual-debug-gate(-detail)` stays MR-only.
