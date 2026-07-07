# agent-stack-shared

A standalone repository of domain-neutral agent rules, skills, commands, and the SDD/TDD
framework layer, shared across UE projects (currently Oathboard and MyRoguelikeGame) and across
tools (Claude Code, Cursor, Codex). Remote: https://github.com/aaron-game-build/agent-stack-shared.

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

Skills (`skills/*/SKILL.md` + non-md assets) and commands (`commands/*.md`) are covered since
batch 2 (see Oathboard's `skills-merge-dossier.md` for the per-item convergence verdicts).
`ue-pie-probe` deliberately stays project-local on both sides (scenario-driven structure), and
each project keeps its own project-only skills/commands untouched by rendering.

## pylib layering (UE-light vs editor-only)

`pylib/` is consumed directly from the submodule via a sys.path shim in each project (e.g.
Oathboard's `oath_project/stack_paths.py`) — it is **not** rendered. Two package classes with
different CI treatment:

- **UE-light** (e.g. `sdd_tdd`): never imports `unreal`; importable and unit-testable in any
  plain Python process. Shared CI and consumer static gates run its tests directly.
- **editor-only** (e.g. `ue_probe`): imports `unreal` at module level and runs inside the UE
  Editor Python environment only. Its package `__init__` must stay import-free so unittest
  discovery and non-editor tooling can traverse it; CI coverage comes from stub-injected unit
  tests (the `tests/` module installs a fake `unreal` before importing) plus a no-project-marker
  boundary test. Never add an editor-only import to a UE-light package.

Shared pylib code is stateless about projects: project values (fail-token prefixes, `Saved/`
subdirectory names, subsystem class paths) are explicit parameters, bound to defaults in each
project's thin wrapper (e.g. `mr_ops/probe_common.py`, `oath_ops/probe_common.py`).

**Not shared** (stays in each project's repo): the `*_ops` binding packages themselves, concrete
`probes/` and `audits/`, `probe_impl` scenario code, domain content suites (e.g. combat
contracts), and project KB modules. These are project content, not tooling.

## Placeholder mechanism (v1)

- `{{KEY}}` — single-value param, inline substitution.
- `{{SLOT:KEY}}` — multi-line slot substitution.
- `<!-- BEGIN OPTIONAL:KEY --> ... <!-- END OPTIONAL:KEY -->` — optional block, removed entirely
  if the project doesn't supply `KEY`.

Full key-by-key semantics and current Oathboard/MR values: `MANIFEST-SCHEMA.md`.

## Sync workflow: `--pull` / `--push`

The unified renderer is `scripts/stack_render.py` in this repo; each consuming project calls it
via a thin wrapper (Oathboard `check_stack.py --pull/--push`, MR `scripts/stack_pull.py`):

- **`--pull`**: read `rules/*.md` from this shared repo, render placeholders using the
  project's local `agent-stack/manifest.json` `shared` node, write the rendered output into the
  project's `agent-stack/rules/`, then trigger the project's existing `--sync` to regenerate
  Cursor/Codex/Claude adapters. Rendered files get a header:
  `<!-- GENERATED from agent-stack-shared; edit there, not here -->`. Any leftover `{{` after
  rendering is a hard error.
- **`--push`** (deliberately conservative): **does not** auto-write back to this shared repo.
  It re-renders in memory and diffs against the project's files. With `--explain`, each dirty
  line is attributed to its origin: inside a slot/param render region → `HINT: change manifest
  slots.X`; in fixed template text → `HINT: edit agent-stack-shared/<file>`. A human then makes
  the edit in the right place. No automatic reverse-rendering.
- **Adapter emission**: a project that sets the manifest `shared.adapters` node gets its
  `.claude/skills/` and `.codex/` thin wrappers generated directly by the renderer (ported
  byte-identical from Oathboard's former `check_stack.py --sync`); projects without the node are
  unaffected. See MANIFEST-SCHEMA §Adapters.

Once a project adopts `--pull`, its local `agent-stack/rules/` stops being hand-edited canonical
content — the Drift Rule in that project's `CLAUDE.md`/`AGENTS.md` needs a one-line update to say
so.

## Integration status

| Project | Consumption | Status |
|---|---|---|
| Oathboard | `agent-stack/scripts/check_stack.py --pull` (manifest: `agent-stack/manifest.json`) → renders rules/sdd/tdd/pylib/skills/commands into `agent-stack/`, then `--sync` generates Cursor/Codex/Claude adapters | **Live** (rules since 2026-07-06, skills/commands since batch 2) |
| MyRoguelikeGame | `scripts/stack_pull.py` (manifest: `.cursor/stack-manifest.json`, `format: mdc` + `ue-` name map) → renders directly into `.cursor/rules|skills|commands` | **Live** (rules merged to main 2026-07-06, skills/commands 2026-07-07) |

## Template Authoring Rules (paid-for lessons — follow when editing this repo)

Distilled from the 2026-07-06/07 convergence retrospective (full analysis: Oathboard
`Docs/agent-knowledge/fable/2026-07-06-shared-stack-retrospective.md`):

1. **One placeholder, one resolution context.** A param used in a markdown link resolves against
   the *output file's* location; used in a JSON value or grep instruction it must be
   project-root-relative; link depth differs between rules (2-deep) and skills (3-deep) output.
   Never reuse one key across these contexts — that was the `KB_ROOT` flaw (fixed in `6f56135`
   by splitting into `KB_ROOT` / `KB_ROOT_FROM_SKILLS` / `KB_ROOT_FROM_PROJECT`).
2. **Command-execution spots take a multi-line slot, not a single-script param.** A single-value
   param silently swallows a project's chained follow-up steps while surrounding prose still
   promises their output (the `CONFIG_SCRIPT` → `CONFIG_RUN_STEPS` regression).
3. **Rendering must be file-level, never directory-wipe.** Shared skill directories legitimately
   mix shared template files with project-only sibling files (runtime scripts, templates,
   examples); a directory rm-then-write deleted six real project files before being caught.
4. **Every convergence replacement ships with a content-loss audit**: diff old vs rendered, list
   each line that exists in old but not new, and tag it *slotted / superseded / lost* — losses
   must be reported, never silent. This audit caught every real regression in both projects. The
   audit surface includes the consumer's CI workflow definitions and modes (a strict-mode gate
   turns soft warnings into a red build — MR's doc-check ran red for a full round this way).
5. **Generalizing a source project's file for sharing loses that project's specifics on
   re-consumption.** When seeding from a project, wrap its project-specific sentences in slots or
   optional blocks up front (`VISUAL_DEBUG_PROJECT_IMPL`, `UIUX_LOCAL_REDIRECT`), don't rewrite
   them into generic prose.
6. **Consumers halt-and-report on template flaws** instead of working around them locally — the
   fix belongs here, next to the schema row that documents it.

The mechanically checkable subset of these rules (OPTIONAL block balance, placeholder↔schema
bidirectional consistency, render smoke on `examples/*.json`) is enforced by
`scripts/template_lint.py`, which runs in this repo's CI on every push/PR.

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
