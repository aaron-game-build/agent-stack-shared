---
name: ue-task-retrospective
description: "复盘最近一个完整任务，筛选值得长期保留的经验教训，并产出知识库写入建议。用于用户要求复盘任务、沉淀知识、总结经验教训、生成知识库更新建议时。先给建议；满足低成本条件时默认推荐 C 全量落盘，待用户确认后再改知识库。"
disable-model-invocation: true
---

# 任务复盘沉淀

将最近一个完整任务复盘为"可长期复用的知识"，并确保沉淀内容有价值、落点正确、下次 Agent 可触达。

## 何时调用

- 用户说"复盘这次任务"
- 用户说"沉淀到知识库"
- 用户说"总结经验教训"
- 用户说"更新知识库建议"
- 用户说"用最近完整任务做知识沉淀"
- 用户报告用户可见 bug、旧功能回归、L3/L4 证据不足，或追问"为什么规则/框架/探针/日志没有拦住"
- 用户指出任务持续很久、内容量很大、涉及多轮调试/多证据包/多 Agent/大提交，询问是否还需要复盘

> 本 skill 默认只产出建议，不直接改知识库。知识库写入需用户确认。

## 开始前

1. 读取 `.ue-py-config.json`
2. 读取 `{{KB_ENTRY_PATH}}` 与 `{{KB_ROOT_FROM_PROJECT}}/concepts/index.md`（若存在）
3. 列出并读取与本次任务最相关的 `modules/*.md`、`concepts/*.md`
4. 若项目已有相近 skill（如 `ue-py-evolve`），读取其 `SKILL.md`，避免职责重复
5. 回顾最近一个完整任务的上下文、计划、关键报错、最终结论

## 复盘目标

只提炼下次 Agent 复用时真正有价值的内容：

- 新的高频陷阱
- 关键根因判断方法
- 可复用的验证路径
- 应进入知识库的决策边界
- 文档缺失、引用缺失、验收口径缺失
- **重要链路的完整正路径**（Happy Path），不只记录出错环节

不要输出流水账。不要只沉淀"失败环境"而漏掉整条可复用链路。

## 工作流

### 1. Extract

按下面维度提取候选知识：

- 问题现象
- 根因
- 证据
- 修复/决策
- 验收方式
- **Accepted Direction**（用户当时认可的实现方向是什么？）
- **Agent Deviation**（Agent 是否擅自换路、叠复杂方案、未目视验证？）

若只是一次性执行细节，先保留为候选，不要直接判定为应沉淀。

**Agent Deviation 优先沉淀到规则/skill**：若根因是"擅自换实现方向"而非单纯 UE API 不懂，Route 应指向 `rules/` 或 `skills/`，不要只写一条 §5 技术坑。

### 2. Filter

对每条候选知识做价值门禁：

- 删掉后，下一个 Agent 会明显更容易走弯路吗？
- 这是通用模式，还是一次性项目噪声？
- 它是否已被 `knowledge-base-entry.md` 或现有模块覆盖？
- 它是"规则/模式/坑"，还是"某次运行中的临时现象"？

满足下列任一条件，通常不写入长期知识库：

- 临时日志内容
- 一次性路径、时间戳、会话 ID
- 仅对当前任务有效的琐碎步骤
- 已被现有知识库表达清楚的重复结论
- **纯 Agent 行为偏差**且已有对应 rule/skill 可表达 → 优先更新规则/skill，KB 只保留交叉引用
- **规则缺失 / 全库链接漂移 / checklist 与 rules 不一致** → Route 到 `/ue-doc-audit` 或更新 [agent-doc-governance.md]({{KB_ROOT_FROM_SKILLS}}/modules/agent-doc-governance.md)

### 2b. Chain Completeness（链路完整性）

若候选知识涉及一条**重要运行链路**，不能只记录出错环节，还必须评估是否需要沉淀**完整正路径**。

**检查（任一为"是"则应补链路沉淀）：**

- 这是后续 Agent 会反复触碰的核心链路吗？（如 setup → 配置 → 运行时 → 验收）
- 现有 KB 是否只写了某个 `pitfall:`，但没有 Happy Path / 步骤表？
- 若只修当前坑，链路**另一环**出错时是否仍会误判？
- 是否需要区分**并行子链**？（例：不同系统的独立链路不应混为一谈）

**若需要沉淀完整链路，候选必须包含：**

| 要素 | 说明 |
|------|------|
| 正路径 | Setup → Asset → Runtime → Validation 的步骤表或简图 |
| 可验证信号 | 每一环 Agent/人可执行的检查点（日志、Editor 状态、L3/L4） |
| 失败现象 | 每一环断了时的典型表现（与下一环区分） |
| 与坑的关系 | 哪些条目是 `pitfall:`，哪些是 `concept:` 正路径 |

**落点建议：** 模块页新增「§端到端链路」+ 概念页拆子链；`knowledge-base-entry.md` §5 只保留单行入口并链到模块。

### 3. Route

为保留下来的知识选择落点：

| 类型 | 落点 |
|------|------|
| **Agent 行为约束**（方向锁定、可视化门禁、micro-ReAct） | `rules/` |
| **特定工作流**（可视化 Debug、复盘、evolve、文档审查） | `skills/<name>/`（全栈漂移 → `/ue-doc-audit`） |
| **稳定概念** | `{{KB_ROOT_FROM_PROJECT}}/concepts/` |
| **完整案例 / 验收** | `{{KB_ROOT_FROM_PROJECT}}/modules/` |
| **通用陷阱速查** | `knowledge-base-entry.md` §5（分类入口 + 链到 concept/module） |

{{SLOT:RETROSPECTIVE_ROUTE_EXTRA_ROWS}}

若没有清晰落点，优先给出"新增模块"建议，而不是硬塞进不相关章节。

- 稳定概念、可教学的定义 → `concepts/<slug>.md`（见 [ue-py-evolve/tagging.md](../ue-py-evolve/tagging.md)）
- 完整案例与取证 → `modules/<topic>.md`

### 3b. Tag（概念标签）

对每条保留的候选，输出推荐标签（供 evolve 写入 frontmatter）：

| 字段 | 说明 |
|------|------|
| `tags` | 如 `concept:...`、`pitfall:...` |
| `related_concepts` | 已有概念页路径，或"建议新建 `<slug>`" |
| `双向链接` | 案例 ↔ 概念各补什么链接 |

规则：只标签化稳定概念/陷阱/API/脚本名；禁止时间戳、一次性探针路径。

### 4. Reachability Check

每条建议都要检查"下次是否读得到"：

- 若写入模块文档，`knowledge-base-entry.md` 是否已有入口？
- 若模块存在但入口不明显，是否需要在 `knowledge-base-entry.md` 增加交叉引用？
- 章节标题是否能让 Agent 快速定位？

不能只写"放某文件"，必须说明为什么下次能被读到。

### 5. Propose First

先输出建议，不直接修改知识库。除非用户明确确认要落盘（如回复 **C**、"全落实"、"直接 evolve"）。

### 5b. 默认建议动作（A/B/C）

**不要机械推荐 B。** 候选经 Filter 后，按下列条件选默认推荐：

#### 默认 **C（Recommended）** — 全部候选落盘

当**同时**满足：

| 条件 | 说明 |
|------|------|
| 条目数 | 保留候选 **≤ 8** 条（含 Happy Path / rule 微门禁条目） |
| 落点类型 | **仅** `concepts/`、`modules/`、`knowledge-base-entry.md` §5、`rules/*`、`concepts/index.md` / `tag-index`；无新 ADR、无删包、无 C++ 产品改动 |
| 置信度 | 每条有**代码 / 日志 / L3/L4** 证据；"不建议沉淀"中无与候选矛盾的未决猜测 |
| Phase B | 无必须同步晋升的大块 Python ops/workflow（docstring 级补充除外） |

此时输出：

```markdown
## 建议动作
- **C. 写入全部候选条目（Recommended）** — 纯 KB/rule/index，≤N 条，一次性落盘成本低
- A. 仅保留候选，不写知识库
- B. 仅写入部分条目（仅当用户明确想减量时）
```

用户已说"沉淀 / evolve / 全落实 / 按 C 做" → **跳过 A/B 讨论，直接执行 C**（或交 `/ue-py-evolve`）。

#### 仍推荐 **B** 的情况

- 候选 **> 8** 条，或混合"高价值 + 低置信/重复/待合并"
- 落点含 **新模块全文**、**ADR**、**Plan 口径变更**、**资产删改**（须用户 L4）
- 与现有 KB **大段重复**，需合并重写而非追加
- 用户明确"先少写 / 只写最关键的"

#### **A** 的情况

- Filter 后无保留候选；或任务纯一次性、无可复用模式

> **原则**：复盘的价值在"下次 Agent 读得到"；对 **doc-only、已筛过、有证据** 的小批量候选，**全写成本通常低于** 用户再选 B 后补 C 的二轮对话。

## 输出格式

使用以下结构：

```markdown
## 候选沉淀

### 1. <知识点标题>
- 价值判断：<为什么值得长期保留>
- 证据来源：<代码 / 日志 / 用户验收现象>
- 建议落点：<文件 + 章节>
- 建议写法：<1-4 行精炼文本>
- 链路完整性：<是否需要沉淀完整链路；若需要，列出环节与子链划分>
- 可触达性：<为什么下次 Agent 能读到；若不够，需补什么引用>
- 推荐标签：<concept:...> <pitfall:...> 等>
- 概念链接：<已有 concepts/xxx.md 或 建议新建>
- Phase B 建议：<若涉及 Python 原子化，是否建议 evolve 执行 Phase B；不必等用户另说"处理 PhaseB">

## 正路径摘要（若 2b 适用，单独一节）

（表格：阶段 | 检查点 | 失败时常见现象）

## 不建议沉淀

- <内容>：<为什么不应进入长期知识库>
- 调试插桩 / session 日志：见 SKILL「落盘前检查」，勿写入 KB

## 建议动作

（按 §5b 选默认推荐；**低成本 doc-only 批次默认标 C Recommended**，勿机械推 B。）

- A. 仅保留候选，不写知识库
- B. 写入部分高价值条目（候选 >8、含 ADR/删包、或用户要求减量时）
- C. 写入全部候选条目（**Recommended** 当：≤8 条 + 仅 KB/rule/index + 证据齐全）
```

## 编写要求

- 保持精炼，优先写规则、模式、验收口径
- 不写任务流水账
- 不写会随时间快速失效的细节
- 不要把"调试过程"原样搬进知识库，要提炼成"判断方法"
- 若某条知识已存在，输出"建议补充/重写现有章节"，而不是重复新增
- 涉及核心链路时，**必须**同时评估 Happy Path；禁止只新增单行坑而不补链路表

## 与 ue-py-evolve 的分工

- `ue-task-retrospective`：筛选候选 + **链路完整性** + 落点建议；候选中标注是否建议 **Phase B**
- `ue-py-evolve` Phase A：用户确认后写入 KB
- `ue-py-evolve` Phase B：**自动评估**是否晋升 Python（用户无需另说"处理 PhaseB"）

若用户直接要求"改知识库"，可先用本 skill 形成候选，再执行 `ue-py-evolve`。

## 落盘前检查（若本次任务含调试 / C++ 插桩）

复盘产出交给 `ue-py-evolve` 落库前，在「不建议沉淀」之外确认：

- [ ] 已移除临时调试 C++（如自定义调试日志宏、NDJSON 写盘、`#region agent log`）
- [ ] 已撤销仅为调试加的 `Build.cs` include path / 临时模块
- [ ] 若改过 C++：关 Editor 后 Build 脚本**仍通过**（防 `C4335` 等行尾问题）
- [ ] 未把 session 日志路径、debug 文件名写入 KB

> evolve 落盘时同样执行；见 [ue-py-evolve/SKILL.md](../ue-py-evolve/SKILL.md)「落盘前检查」。

## 附加资源

- 复盘样例：[examples.md](examples.md)
- 标签与概念页规范见 [ue-py-evolve/tagging.md](../ue-py-evolve/tagging.md)

<!-- BEGIN OPTIONAL:FIVE_LAYER_GUARDRAIL -->
## Escaped bug：五层 guardrail 横向泛化

用户可见回归时，读 [incident-to-guardrail-retrospective.md]({{KB_ROOT_FROM_SKILLS}}/modules/incident-to-guardrail-retrospective.md)（五层定义、必答问题、项目化示例的权威来源），在此基础上补做以下增量步骤：

**Local Fix Generalization Gate**：若逃逸 bug 揭示了一类可复用的根因，除了修复本次具体实例，还要显式列出同类根因在其他表面是否存在——**checked**（已检查确认无问题）、**intentionally excluded**（明确排除且说明理由）、**deferred**（延后处理但已记录）三类之一。典型同类表面包括：不同 actor/方向、不同技能/能力族、新旧 tag pair、通用/专属路径、fallback 路径、Blueprint/DataAsset 变体、AI/玩家两份拷贝。这一步控制的是"扫描范围"，不要求本次任务修完所有同类项，但残留项必须显式列出，不能沉默略过。

对视觉呈现类事故，机制、可读性、性能三类证据要分开举证，不能互相替代：

- **机制**：cue 归属、命中结果、状态/Status、旁路日志。
- **可读性**：目标区域多帧截图、contact sheet/视频、人工 L4 备注。
- **性能**：Niagara/组件计数、活跃实例数、stat 采样，或明确的 CPU/GPU 预算。

绿色的机制日志、缺失的截图峰值、或平均截图偏移，都不能替代另外两类证据。

**必须输出的表格**（五层定义本身参见上面链接的模块文档，这里只要求落地成表）：

```markdown
## Five-layer guardrail analysis

| Layer | Status | Evidence | Guardrail candidate | Route |
|---|---|---|---|---|
| Rule | Missing / Weak / Passed / N/A | ... | ... | ... |
| Framework | Missing / Weak / Passed / N/A | ... | ... | ... |
| Runtime and validation | Missing / Weak / Passed / N/A | ... | ... | ... |
| Log and evidence | Missing / Weak / Passed / N/A | ... | ... | ... |
| Retrospective | Missing / Weak / Passed / N/A | ... | ... | ... |
```

如果用户已经明确说"开始 / 落盘 / 固定到规则或 skill"，对纯文档护栏跳过 A/B/C 建议流程的反复讨论，直接落实已经谈妥的路由。保持常驻规则精简；完整模板留在本 skill 和 incident 模块里。
<!-- END OPTIONAL:FIVE_LAYER_GUARDRAIL -->

<!-- BEGIN OPTIONAL:LONG_TASK_GOVERNANCE -->
## Long-task governance analysis

当任务持续很久，或以一次大提交/推送收尾时，做以下检查（自足内联，不要求项目必须有专属治理模块）：

- **Scope audit**：任务实际扩展到了哪些范围？还有哪些明确排除在外？
- **Evidence layering**：哪些证据分别证明了机制、运行时生命周期、截图状态、人工 L4/观感？
- **Multi-agent reconciliation**：如果有子任务/子 Agent 产出证据，主 Agent 采纳了哪些、拒绝了哪些、被后续结果取代了哪些？
- **Commit scope**：提交前是否应该给用户看一份 Included / Excluded / Large assets / Evidence / Residuals 清单？
- **Residual routing**：哪些非阻塞问题应该归入调优 backlog，而不是当前任务的阻塞项？（若项目配置了技术债登记簿，按「技术债路由」节落账）

若长任务中同时出现了逃逸 bug，五层 guardrail 表和 long-task governance 摘要都要输出，不要用一个替代另一个。

{{SLOT:LONG_TASK_GOVERNANCE_LINK}}
<!-- END OPTIONAL:LONG_TASK_GOVERNANCE -->

<!-- BEGIN OPTIONAL:TECH_DEBT_ROUTING -->
## 技术债路由

复盘收尾时，把以下三类**非阻塞残留**记入项目技术债登记簿 `{{TECH_DEBT_REGISTER_PATH}}`，
不要只留在复盘输出或提交信息里：

- **未验证路径**：DryRun/静态验证过但从未实跑、L3 只覆盖了部分分支、验证依赖尚不存在的条件（如另一个项目解冻、第三消费方接入）
- **降级/延后决定**：为收敛当前任务而明确接受的次优实现、留待触发条件成熟再处理的问题
- **已知但不修**：基线遗留、外部依赖缺陷、与当前方向冲突而搁置的项

每条按登记簿现有表格式落账：scope、标题、记入日期、**复查触发条件（事件驱动优先于日期）**、状态。
已有同项条目则更新其状态/触发条件，不重复记。债务被清偿或转为正式任务时改 `closed`/`converted`，
不删行。

判别口径：会被下一个 Gate 收口或 doc-audit 追问「这个验过没有」的事 → 登记簿；
纯知识/坑 → KB（走 evolve）；两者都是 → 各记一条并互链。
<!-- END OPTIONAL:TECH_DEBT_ROUTING -->

<!-- BEGIN OPTIONAL:ESCAPED_BUG_ADDENDUM -->
## Escaped-bug addendum：收尾前先泛化

任何有可复用根因类别的逃逸 bug，复盘都必须包含一次横向泛化检查。不要把教训只写成一个具体 bug（例如"旧 tag X 错了"），而要重新表述为一类契约问题，然后把同类表面逐一列为 checked / excluded / deferred。

这一步在以下场景尤其重要：一次局部修复可能在另一个 actor、能力族、data asset、Blueprint/native 路径、探针路径、fallback 路径，或呈现/运行时层留下残留问题时。
<!-- END OPTIONAL:ESCAPED_BUG_ADDENDUM -->
