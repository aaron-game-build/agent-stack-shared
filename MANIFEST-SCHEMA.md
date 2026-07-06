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
| `KB_ROOT` | agent-react.md, human-validation-handoff.md, agent-doc-safety.md (link), commands/ue-doc-audit.md | KB root for **markdown links as seen from rules/commands output** (2 levels deep in Oathboard; `mdc:` scheme in MR is depth-independent) | `../../Docs/agent-knowledge` | `mdc:docs/ue-agent-knowledge` |
| `KB_ROOT_FROM_SKILLS` | skills/* SKILL.md link contexts | KB root for **markdown links as seen from skills output** (3 levels deep: `<skills_dir>/<name>/SKILL.md`). Split from KB_ROOT after Oathboard's rendered skill links were found silently broken (2-deep value used at 3-deep location) | `../../../Docs/agent-knowledge` | `mdc:docs/ue-agent-knowledge` (draft) |
| `KB_ROOT_FROM_PROJECT` | agent-doc-safety.md (grep), ue-py-init (dir layout + JSON config values), ue-py-evolve (dir tree, path rule), ue-task-retrospective (read/route plain paths) | KB root as a **plain project-root-relative path** (no `../`, no link scheme) — for JSON values written to root-level config, grep instructions, and route-destination tables | `Docs/agent-knowledge` | `docs/ue-agent-knowledge` (draft) |
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
| `GIT_CLAIM_TOOL_NOTE` | agent-concurrency.md | Trailing note after "Git index/commit/LFS 写入先 claim" naming the project's claim-enforcement tool, e.g. `，并用 \`scripts/mr-git --\`（默认 \`--check-claims\`）` — or empty. Template carries no stub | empty | `，并用 \`scripts/mr-git --\`（默认 \`--check-claims\`，严格告警加 \`--strict\`）` |
| `DELEGATION_AGENT_POOL` | agent-delegation-cost.md | Named cheap-model subagents/tools available for delegation. Include the model guidance inside the value (e.g. `（模型选 sonnet/haiku）`) — the template adds no model note of its own | (Oathboard draft — general-purpose subagent w/ sonnet/haiku; no named coder tool yet) | `pie-probe-runner subagent`、Codex `mr-coder` |

## Optional blocks

| Key | Used in | Semantics | Oathboard | MR (draft) |
|---|---|---|---|---|
| `PROTECTED_CONTRACTS` | agent-react.md | Renders the Protected Contract paragraph when the project maintains a protected-contract list | Not configured (block omitted) — candidate future use: `Run*Validation` API / `validate_runtime_source_static.py` hardcoded deps | Configured — refs MR's `protected-contract-framework.md` + `feature-contract-regression-governance-plan.md` + `combat-core-regression-governance-plan.md` |
| `PROTECTED_CONTRACTS_REFS` | agent-react.md (inside the optional block) | Link list rendered inside the Protected Contract paragraph | n/a (block omitted) | `[feature](mdc:docs/plans/feature-contract-regression-governance-plan.md)`、`[combat-core](mdc:docs/plans/combat-core-regression-governance-plan.md)` |
| `CODEGRAPH_DETAIL_DOC` | codegraph.md | Link to a project's detailed codegraph-indexing concept doc; omitted → block removed, rule stays inline-only | Not configured (Oathboard keeps the inline-only version per decision D1) | `[codegraph-indexing.md](mdc:docs/ue-agent-knowledge/concepts/codegraph-indexing.md)` (draft) |
| `PROJECT_DIRECTION_LOCKS` | agent-contracts.md §2 | Project-level accepted-direction defaults that must not be switched without user confirmation (multi-line; e.g. MR's DrawDebug ground-circle default and top-down WASD/aim lock). Omitted → whole block removed | Not configured | Configured — DrawDebug 范围圈默认 + 俯视 WASD/朝向 Phase 8.1 方向锁 |
| `PROJECT_TEST_NOTES` | agent-react.md Test section | One extra project-specific Test-stage behavior line (e.g. MR's "L4/手感需独占 editor 时自动开图"). Omitted → block removed | Not configured | Configured — auto-open target map when L4 needs exclusive editor |
| `PROJECT_DELEGATION_NOTES` | agent-delegation-cost.md tail | Project-specific delegation cross-references (read-first playbooks, orchestration handbook links). Omitted → block removed | Not configured | Configured — pie-probe-playbook read-first + prune-pass/orchestration links |

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

## Skills/Commands placeholders

Added when `skills/*/SKILL.md` and `commands/*.md` were seeded into this repo (2026-07-06), per
Oathboard's `Docs/agent-knowledge/fable/skills-merge-dossier.md` merge dossier. These are **not**
yet wired into `scripts/stack_render.py` — that renderer currently only handles `rules`/`sdd`/
`tdd`/`pylib` targets. Extending it to also render `skills/`/`commands/` is separate future work;
this section only documents the placeholder keys the seeded templates already use, so that
extension has a ready-made key list. Same three-mechanism convention as above (`{{KEY}}` /
`{{SLOT:KEY}}` / `OPTIONAL:KEY`).

### Params (single-value)

| Key | Used in | Semantics | Oathboard value | MR value (draft) |
|---|---|---|---|---|
| `KB_ENTRY_PATH` | ue-py-run, ue-doc-audit | Relative link to the project's `knowledge-base-entry.md` from inside `agent-stack/skills/<name>/SKILL.md` | `../../../Docs/agent-knowledge/knowledge-base-entry.md` | `../../../docs/ue-agent-knowledge/knowledge-base-entry.md` (draft) |
| `KB_ROOT_FROM_SKILLS` / `KB_ROOT_FROM_PROJECT` | ue-py-init, ue-py-evolve, ue-doc-audit, ue-task-retrospective | Skills templates use the two split params (see the Params table above) — link contexts take `KB_ROOT_FROM_SKILLS`, plain-path/JSON contexts take `KB_ROOT_FROM_PROJECT`. The former single `KB_ROOT` reuse documented here was the design flaw fixed in 6f56135 | see Params table | see Params table |
| `UIUX_LOCAL_REDIRECT` (slot) | ui-ux-pro-max | Trailing sentence of the header note redirecting local UI work to project docs — or a generic fallback sentence | `宿主项目若有本地 UI 设计系统文档，优先走项目文档。` | MR original two-doc redirect (mr-ui-kit-design-system.md + ui-validation-orchestration.md) |
| `UE_PY_RUN_SCRIPT_PATH` | ue-py-init | Path to the `ue_python.py` runner written into `.ue-py-config.json`'s `ue_python_script` field | `agent-stack/skills/ue-py-run/scripts/ue_python.py` | `.cursor/skills/ue-py-run/scripts/ue_python.py` (draft) |
| `SYNC_WRAPPERS_COMMAND` | ue-py-init (optional block), ue-doc-audit (skill + command, optional block) | Exact command to regenerate Cursor/Codex/Claude adapter wrappers after a canonical edit | `python agent-stack/scripts/check_stack.py --sync` | not applicable yet — MR has no `--sync` producer until it migrates off hand-edited `.cursor/` (draft: TBD) |
| `PY_OPS_PACKAGE` | ue-py-evolve | Name of the project's promoted-Python-ops package under `Content/Python/` (Phase B target) | `oath_ops` | `mr_ops` (draft) |
| `PY_OPS_ARCHITECTURE_DOC` | ue-py-evolve | Filename (under `{{KB_ROOT}}/modules/`) of the ops-architecture index doc that Phase B promotions must update | not yet named (Oathboard has no equivalent doc today; candidate name TBD) | `python-ops-architecture.md` (draft) |
| `UE_PY_EVOLVE_SCRIPTS_DIR` | ue-py-evolve, ue-doc-audit (skill + command) | Path to the `ue-py-evolve` skill's `scripts/` dir, containing `knowledge_graph_check.py` / `agent_stack_check.py` | `agent-stack/skills/ue-py-evolve/scripts` | `.cursor/skills/ue-py-evolve/scripts` (draft) |
| `PROJECT_ROOT` | ue-doc-audit (command), ue-py-extend | Absolute project root, used in `cd`/compile commands | `G:/UEProjects/Oathboard` | `G:/UEProjects/MyRoguelikeGame` (draft) |
| `ENGINE_ROOT` | ue-py-extend | Absolute engine root (`Engine/` dir), used in compile commands | `G:/UnrealEngine/UE_5.7/Engine` | draft — same machine, same value until MR pins its own engine build |
| `PROJECT_NAME` | ue-py-extend | Project short name, used to build `<Project>Editor` target and `.uproject` filename | `Oathboard` | `MyRoguelikeGame` (draft) |
| `BUILD_WORKFLOW_DOC` | ue-build-launch, ue-build-no-config | Link target for the project's build/launch workflow doc, read before running the script | not yet named (Oathboard has no dedicated doc yet; candidate: a new `Docs/agent-knowledge/modules/build-and-launch-workflow.md`) | `docs/ue-agent-knowledge/modules/build-and-launch-workflow.md` (draft) |
| `BUILD_LAUNCH_SCRIPT` | ue-build-launch, ue-build-no-config, ue-launch-config | Absolute path to the root `Build-And-Launch.ps1` wrapper script (S1 decision: Oathboard adopts MR's external-script pattern) | not yet created — **S1 follow-up**: Oathboard needs its own `Build-And-Launch.ps1` before this param has a real value | `G:/UEProjects/MyRoguelikeGame/Build-And-Launch.ps1` (draft) |
| `CONFIG_RUN_STEPS` (slot) | ue-python-config | Full multi-line command block for step 4 — the `-f` config script invocation PLUS any chained follow-up gates (e.g. Oathboard runs `validate_all_static.py` after `setup_gate0_map.py`). Replaces the former single-script `CONFIG_SCRIPT` param, which silently dropped chained steps | `python $uePy -f (Join-Path $PWD "Content/Python/setup_gate0_map.py")` + chained `python Content/Python/oath_project/validate_all_static.py` | `python $uePy -f (Join-Path $PWD "Content/Python/final_phase1_config.py")` (draft) |
| `PROJECT_WINDOW_TITLE` | ue-live-coding | Editor window title `AppActivate` looks for | `Oathboard` | `MyRoguelikeGame` (draft) |

### Slots (multi-line)

| Key | Used in | Semantics | Oathboard value (extracted from current skill/command) | MR value (draft) |
|---|---|---|---|---|
| `DOC_AUDIT_TRIGGERS` | ue-doc-audit (skill + command) | "何时必须跑" trigger row(s) for the doc-audit timing table/list | `Gate 0 L4/H 签核前 \| **建议**` | `Phase N L4 通过、roadmap 标完成前 \| **是**` (draft; MR treats this trigger as mandatory rather than advisory) |
| `DOC_AUDIT_RELATED_LINKS` | ue-doc-audit (skill) | "相关" section trailing link(s) beyond the shared `tagging.md`/KB-entry links | `[static-validation-index.md](../../../Docs/validation/static-validation-index.md)` | none extra beyond KB entry §Agent 规则索引 (draft) |
| `RETROSPECTIVE_ROUTE_EXTRA_ROWS` | ue-task-retrospective | Project-specific extra Route table rows beyond the five shared categories (SDD/FeatureSpec, probes/TDD, etc.) | `\| SDD / FeatureSpec \| Docs/production/features/ + feature_specs.py \|`<br>`\| 探针 / TDD \| agent-stack/tdd/、Content/Python/probes/、oath_ops/probe_targets.py \|` | GAS/Phase1 asset automation, skill-test-arena, validation-checklist, quality-gates, build-and-launch rows — see MR SKILL.md §3 bullet list (draft, needs condensing into table rows) |
| `LONG_TASK_GOVERNANCE_LINK` | ue-task-retrospective (inside OPTIONAL:LONG_TASK_GOVERNANCE) | Optional trailing sentence pointing to a project's own long-task-governance module; may be empty (block is self-contained without it) | empty (Oathboard has no dedicated module yet) | `完整背景见 [long-task-governance-retrospective.md](../../../docs/ue-agent-knowledge/modules/long-task-governance-retrospective.md)。` (draft) |
| `PYTHON_CONFIG_BOUNDARY_DOC` | ue-python-config (command) | Link text+target for the "automation boundary" doc read at step 1 | not yet named (Oathboard candidate: `static-validation-index.md`) | `[python-gas-asset-limits.md](../../docs/ue-agent-knowledge/concepts/python-gas-asset-limits.md)` (draft) |
| `BUILD_REPORT_FORMAT` | ue-build-launch, ue-launch-config, ue-python-config | What the agent must report back after running the build/launch/config script (exit codes, tokens, MANUAL items) | `Build exit code、Remote Exec 是否响应、配置脚本是否打印 OATHBOARD_ALL_STATIC_OK` | `Build 是否成功（exit code）、Editor 是否在 180s 内响应 Remote Exec、final_phase1_config.py 输出中的 [OK]/[MANUAL]/[ERR]` (draft) |
| `LIVE_CODING_PRE_READ_LINK` | ue-live-coding | Second pre-read item (first is always the "confirm no .h changes" line); project's build/live-coding workflow doc | `[static-validation-index.md](../../Docs/validation/static-validation-index.md)` | `[build-and-launch-workflow.md](../../docs/ue-agent-knowledge/modules/build-and-launch-workflow.md) §Live Coding 适用判定` (draft) |
| `RELATED_RUNTIME_DEBUG_LINKS` | ue-live-coding | "相关" section: links to project-specific runtime/PIE debug entry points | `Gate 0 运行时验证 → /ue-pie-probe` | `GAS 激活调试：PIE 下 /ue-pie-probe 或 dump_asc_activation_specs.py`、`[gas-input-tag-activation.md](../../docs/ue-agent-knowledge/concepts/gas-input-tag-activation.md)` (draft) |

### Optional blocks

| Key | Used in | Semantics | Oathboard | MR (draft) |
|---|---|---|---|---|
| `ALREADY_INITIALIZED_GUARD` | ue-py-init | Renders a warning paragraph when the project's `ue-py-init` is mostly for re-init/path-repair on an already-initialized repo, not first-time setup. Slot `ALREADY_INITIALIZED_GUARD_TEXT` carries the actual sentence | Configured — `ALREADY_INITIALIZED_GUARD_TEXT`: `**Oathboard 主仓库已有** \`.ue-py-config.json\` 与 \`Docs/agent-knowledge/\` — 勿覆盖现有 [\`knowledge-base-entry.md\`](../../../Docs/agent-knowledge/knowledge-base-entry.md)。` | Not configured (MR's `ue-py-init` still targets genuine first-time setup; block omitted) |
| `SYNC_WRAPPERS_STEP` | ue-py-init, ue-doc-audit (skill + command) | Renders the "同步 agent-stack wrappers" closing step that calls `check_stack.py --sync`, reusing the same `SYNC_WRAPPERS_COMMAND` param inside | Configured — Oathboard already produces Cursor/Codex adapters via `--sync` | Not configured yet — enable once MR migrates to `--pull` and gets its own `--sync` producer |
| `FIVE_LAYER_GUARDRAIL` | ue-task-retrospective | Renders the escaped-bug five-layer guardrail addendum (Local Fix Generalization Gate + required output table), deduplicated against the project's own five-layer module (linked via `{{KB_ROOT}}`, not re-defined inline) | Configured — links to `incident-to-guardrail-retrospective.md` (36-line module, already has the five-layer table + required questions + Oathboard examples; this block only adds the increment MR had beyond that: the Generalization Gate + visual-evidence 3-way split + output-table template) | Configured (draft) — MR's own `.cursor/skills/ue-task-retrospective/SKILL.md` originated this content; once MR adopts the shared skill it would link its own five-layer module the same way |
| `LONG_TASK_GOVERNANCE` | ue-task-retrospective | Renders the long-task governance checklist (scope audit, evidence layering, multi-agent reconciliation, commit scope, residual routing). Self-contained; `{{SLOT:LONG_TASK_GOVERNANCE_LINK}}` may be left empty | Configured — Oathboard has no dedicated module yet, so `LONG_TASK_GOVERNANCE_LINK` renders empty; the checklist itself still applies | Configured (draft) — MR has `long-task-governance-retrospective.md`, so its `LONG_TASK_GOVERNANCE_LINK` would point there |
| `ESCAPED_BUG_ADDENDUM` | ue-task-retrospective | Renders the closing "generalize before closing" reminder for any escaped bug with a reusable root-cause class | Configured — generic wording, no project-specific content needed | Configured (draft) — same generic wording applies |
| `VISUAL_DEBUG_PROJECT_IMPL` | ue-visual-debug | Project reference-implementation paragraphs after the Smallest-Change table (API names, multi-state color semantics, project KB links). Added so MR's own implementation notes (`RegisterCombatDebugFlash`, block-flash vs held-E-circle distinction) survive shared consumption | Not configured (Oathboard has no impl yet) | Configured — MR original 参考实现 + CombatRoom 五色 paragraphs verbatim |

### Notes on this section

- `PY_OPS_ARCHITECTURE_DOC` and `BUILD_WORKFLOW_DOC` currently have **no real Oathboard value**
  because Oathboard has neither an ops-architecture index doc nor a build-workflow doc today —
  these are called out as gaps, not guessed at, consistent with the existing convention above.
- `BUILD_LAUNCH_SCRIPT` has no real Oathboard value yet because S1 (adopt MR's external
  `Build-And-Launch.ps1` pattern) is an accepted direction but the script itself has not been
  written in Oathboard's repo — this is tracked as follow-up engineering work, not a documentation
  gap.
- `FIVE_LAYER_GUARDRAIL`'s Oathboard configuration deliberately does **not** duplicate the five
  Layer/Question/Destination rows already in `incident-to-guardrail-retrospective.md` — the
  optional block links out to that module and only adds the Local Fix Generalization Gate and the
  output-table requirement, which that module does not yet have.
