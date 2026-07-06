# Manifest Schema — `shared` Node

This document describes every placeholder key used across `rules/*.md` in this shared
repository, and how a consuming project supplies values for them via the `shared` node in its
local `agent-stack/manifest.json`.

## Placeholder syntax (v1)

- **Param** — `{{KEY}}`: single-value inline substitution.
- **Slot** — `{{SLOT:KEY}}`: multi-line text substitution (a paragraph, a list, a table body).
- **Optional block** — `<!-- BEGIN OPTIONAL:KEY --> ... <!-- END OPTIONAL:KEY -->`: the whole
  block is removed if `KEY` is not provided in the project's `optional` map; otherwise the
  block is kept and any placeholders inside it are still rendered.

After rendering, any leftover `{{` in the output is a hard error (missing key).

## `shared` node shape (project-side `agent-stack/manifest.json`)

```json
{
  "shared": {
    "repo": "G:/UEProjects/agent-stack-shared",
    "params": { "KEY": "value" },
    "slots": { "KEY": "multi-line\ntext" },
    "optional": { "KEY": "value or block-trigger content" }
  }
}
```

## Params (single-value)

| Key | Used in | Semantics | Oathboard value | MR value (draft) |
|---|---|---|---|---|
| `AUDIT_Q2_TARGET` | agent-react.md | What Audit question 2 points readers to for known pitfalls/scope | `current-validation-lock.md` | `knowledge-base-entry.md` §5 陷阱 |
| `KB_ROOT` | agent-react.md, human-validation-handoff.md, agent-doc-safety.md | Project KB module root, used to build relative links | `../../Docs/agent-knowledge` | `../../docs/ue-agent-knowledge` (draft) |
| `CODEGRAPH_PROJECT_PATH` | codegraph.md | Absolute project root passed to `codegraph sync` / MCP `projectPath` | `G:/UEProjects/Oathboard` | `G:/UEProjects/MyRoguelikeGame` (draft) |
| `CODEGRAPH_PATH_FALLBACK` | codegraph.md | Windows PATH fallback for the `codegraph` CLI when not on PATH | `C:\Users\jzd94\AppData\Roaming\npm\codegraph.cmd` | `C:\Users\jzd94\AppData\Roaming\npm\codegraph.cmd` (draft, same machine) |
| `UTF8_MARKERS_TOOL` | agent-doc-safety.md | Project-specific script for editing ASCII marker blocks in Chinese docs | `oath_utf8_markers.py` | not applicable — MR has no equivalent tool yet (draft: TBD, may reuse Oathboard's script or omit) |

## Slots (multi-line)

| Key | Used in | Semantics | Oathboard value (extracted from current rule) | MR value (draft) |
|---|---|---|---|---|
| `QUALITY_GATES_LINKS` | agent-react.md | Link(s) to the L1–L4/H quality gate doc(s) | `[development-quality-gates.md](../../Docs/agent-knowledge/modules/development-quality-gates.md)` | `[gates](mdc:docs/ue-agent-knowledge/modules/development-quality-gates.md)`、`[validation](mdc:docs/ue-agent-knowledge/modules/validation-checklist-core.md)` (draft) |
| `READ_ENTRYPOINTS` | agent-react.md | Files to read at REACT "Read" stage | `` `.ue-py-config.json`、`Docs/agent-knowledge/knowledge-base-entry.md`、`AGENTS.md` `` | `` `.ue-py-config.json`、`knowledge-base-entry.md`、`AGENTS.md` `` (draft) |
| `BASELINE_ADR_LINK` | agent-react.md | Link to the tech-stack/AI-boundary baseline ADR | `[ADR-0001](../../Docs/design/decisions/0001-tech-stack-and-ai-boundary.md)` | ADR-0001 equivalent (draft — MR link not yet confirmed) |
| `AUDIT_SCOPE_QUESTION` | agent-react.md | Domain-specific scope question for Audit stage 1 | `Gate 0 范围是否越界` | `§5 陷阱` (draft; MR phrases this as a pitfall check rather than a scope check) |
| `CARRY_MICRO_GATES` | agent-react.md | Full micro-gate trigger list + links, project-specific | `命中 intent 解析、承诺账本、棋盘规则、AI 关系、Editor 探针、commandlet、L4 截图 → 读 [development-quality-gates.md](../../Docs/agent-knowledge/modules/development-quality-gates.md) 与 [static-validation-index.md](../../Docs/validation/static-validation-index.md)。` | `命中角色表现、ARPG spine、Frozen、首次子系统、IK、probe/audit、combo/Status、俯视 WASD、GAS InputTag、目标选择、锁血、probe 常量/新建/改名 → 读 [micro-gates](mdc:docs/ue-agent-knowledge/modules/react-carry-micro-gates.md)` (draft) |
| `PLAN_LOCK_SCOPE` | agent-contracts.md | List of work types that require Plan Lock | `多文件改动、Editor、C++、关卡、批量资产脚本、探针` | `多文件改动、Editor、C++、关卡、GAS、批量资产脚本` (draft) |
| `MAIN_PATH_DOMAIN_EXAMPLES` | agent-contracts.md | Domain examples for "main path" prohibition row | `解析/规则/账本架构或数据流` | `GAS 架构 / 播放路径 / 数据流` (draft) |
| `AUDIT_Q4_QUESTION` | agent-react.md | Audit question 4, project-specific boundary/subsystem check | `是否触及 LLM/规则边界？` | `**首次**接触引擎子系统？→ Lyra diff` (draft) |
| `DIRECTION_SWITCH_EXAMPLES` | agent-contracts.md | Domain examples of silently switching an accepted direction. Value must INCLUDE the surrounding full-width parentheses (e.g. `（DrawDebug→Mesh）`) or be empty — the template has no brackets of its own, so an empty value renders cleanly | empty (no concrete example yet; add one with parentheses on integration if desired) | `（DrawDebug→Mesh、Tag→仅 BindKey）` (draft) |
| `CONCURRENCY_BACKGROUND_LINK` | agent-concurrency.md | Full trailing sentence pointing to the concurrency background doc, e.g. `完整背景见 [x](...)。` — or empty. The template carries no sentence stub, so an empty value renders cleanly | empty (Oathboard has no such doc yet) | `完整背景见 [concurrent-agent-coordination.md](mdc:docs/ue-agent-knowledge/modules/concurrent-agent-coordination.md)。` (draft) |
| `CONCURRENCY_SERIAL_RESOURCES` | agent-concurrency.md | Project-specific resources that must be serialized | (Oathboard draft on integration, e.g. `Content/Python/oath_project`, root wrapper, task/reload registry) | `` `Content/Python/mr_ops`、root wrapper、task/reload registry `` |
| `CONCURRENCY_SHARED_STACK_TARGETS` | agent-concurrency.md | Shared stack targets no two agents may edit concurrently | (Oathboard draft, e.g. `oath_project` shared scripts, task registry) | `` `mr_ops`、root wrapper、task registry、reload registry `` |
| `DELEGATION_AGENT_POOL` | agent-delegation-cost.md | Named cheap-model subagents/tools available for delegation | (Oathboard draft — general-purpose subagent w/ sonnet/haiku; no named coder tool yet) | `pie-probe-runner subagent`、Codex `mr-coder` |

## Optional blocks

| Key | Used in | Semantics | Oathboard | MR (draft) |
|---|---|---|---|---|
| `PROTECTED_CONTRACTS` | agent-react.md | Renders the Protected Contract paragraph when the project maintains a protected-contract list | Not configured (block omitted) — candidate future use: `Run*Validation` API / `validate_runtime_source_static.py` hardcoded deps | Configured — refs MR's `protected-contract-framework.md` + `feature-contract-regression-governance-plan.md` + `combat-core-regression-governance-plan.md` |
| `PROTECTED_CONTRACTS_REFS` | agent-react.md (inside the optional block) | Link list rendered inside the Protected Contract paragraph | n/a (block omitted) | `[feature](mdc:docs/plans/feature-contract-regression-governance-plan.md)`、`[combat-core](mdc:docs/plans/combat-core-regression-governance-plan.md)` |
| `CODEGRAPH_DETAIL_DOC` | codegraph.md | Link to a project's detailed codegraph-indexing concept doc; omitted → block removed, rule stays inline-only | Not configured (Oathboard keeps the inline-only version per decision D1) | `[codegraph-indexing.md](mdc:docs/ue-agent-knowledge/concepts/codegraph-indexing.md)` (draft) |

## Notes

- All Oathboard values above are the actual current values already present in
  `agent-stack/rules/*.md` at the time this seed was written (2026-07-06).
- All MR values are marked **draft**: they are extracted from `.cursor/rules/*.mdc` for
  reference, but MR has not yet migrated to `--pull` mode, so these are not live/consumed
  anywhere yet — they exist to make `oathboard-manifest-shared-draft.json`'s sibling (an
  eventual `myroguelikegame-manifest-shared-draft.json`) easy to produce later.
- Keys with no current Oathboard value are called out explicitly above so integration doesn't
  silently drop a placeholder — those need a decision at Oathboard `--pull` time, not a guess
  baked into this schema doc.
