# 委派与成本纪律

用于隔离高往返、低结论密度任务，并控制主线上下文膨胀。委派判定按**工作形态**，不看难度。

## 1. 委派判定矩阵

| 工作形态 | 处理 | 理由 |
|---|---|---|
| 结构化代码查询（调用链、定义、影响） | **codegraph 直连，禁委派** | 索引已预建，委派只增往返 |
| 已知 1–2 个文件 | **直接 Read** | 先读目标文件最省成本 |
| 广域扫描（3+ 设计文档 / 关联 / 命名） | **Explore subagent** | 隔离重上下文 |
| PIE / remote-python 的写-跑-读-改循环 | **{{SLOT:DELEGATION_AGENT_POOL}}** | 高往返低结论密度 |
| 单文件编辑 / 单次 grep | **直接做** | 低价值委派 |
| 需 shell（npm/node/python/git/npx） | **主线执行，不委派** | subagent Bash 易静默停止 |

便宜活的省钱杠杆是**模型分级**。

## 2. 预读优先（pre-explore）

1. 委派前先 read 已知 playbook / memory / KB / ADR。
2. 再在已读线索上定向 codegraph/grep。
3. 返程分两段：**已有文档已答** 与 **文档未覆盖/新探索**。

## 3. 委派契约

- Explore：结构化摘要 + 出处（文件:行号），**不返原文**，≤200 行。
- 高往返 subagent（如 PIE probe runner）：只返「绿 token / 失败层级(L3/L4) / 根因 / 改文件」。
- 所有 subagent：先写已覆盖，再写待探索。
- 委派前检查任务描述含 `npm/node/python/git/npx/Bash`：含 → 留主线。

## 4. Subagent 存活检测

`run_in_background: true` 时检查 output 文件 `mtime/size` 和完成标记（done/completed/success/ok/pass/result）。无标记 + `mtime>5min` + `size<=512` 常为静默停止；再核验产物目录，无产物则主线接管，且不重复委派同一 subagent。

## 5. 大批量写入委派便宜 subagent

多文件 / 机械性写入（文档减重、批量 frontmatter、归档移动、跨文件改链接、多文件重构）
**一律委派给能写的 subagent 并指定便宜模型**（{{SLOT:DELEGATION_AGENT_POOL}}），
主线只做判断、定护栏、给精确指令、读结论、跑门禁验收。

- **Why**：旗舰模型单价高，机械写入不需要其判断力。省钱杠杆叠加：既换便宜模型，又隔离上下文。
- **边界**：极小单点写入（一条 memory、一行索引、一个表格加两行）主线直接做，不值得 spawn 开销。
- **委派子 agent 时默认显式指定便宜模型**；不指定会回退到主线旗舰模型。

## 6. 参考 / 映射 / 案例类内容不进 alwaysApply

每回合常驻的工件（alwaysApply 为 true 的规则、AGENTS.md、CLAUDE.md）只放**硬约束**。
参考表、agent 映射、案例、外部材料摘录一律放 KB module 或按需规则（`alwaysApply: false`），按需引用。

- **Why**：常驻工件有字符预算。把参考内容塞进常驻规则会顶爆预算——真实踩过坑：agent
  映射表误入 alwaysApply 的委派规则，当场顶爆上限。

## 7. 加治理配背压

新增任何治理文档 / 规则前先问三件事：
1. 常驻还是按需？（参考 / 映射 / 案例一律按需）
2. 有没有配套的「删」？（加一页就想哪页该归档 / 合并）
3. 元治理改动节奏是否快过产品文档？（治理倒置信号）

> 治理过重的解药不是更多治理，是给增长配背压。

## 8. 主线上下文控制（防 token 暴涨）

**背景**：每轮计费 = 整个对话历史 token × 模型单价。对话越长、每轮越贵。
以下操作最容易让历史膨胀，必须主动规避。

### 8a. Read 大文件前先问自己
- 我真的需要把这 N 行全部载入上下文吗？
- 能否先 `grep -n` 定位行号，再只 `Read offset=X limit=Y` 读必要段？
- **原则**：只 Read 你确实要用于判断或编辑的行，其余走 grep/Bash 抽取。

### 8b. 大文件改写用脚本，不走 Edit/Read
改写超过 50 行的文件，用脚本操作（slice + 拼接），不把文件内容 Read 进主线再 Edit。

### 8c. Explore subagent 的 prompt 必须加硬约束
委派 Explore 时在 prompt 结尾加：
```
返回格式硬约束：每条结论 ≤1 行 + 出处路径，禁止贴完整代码/配置原文，禁止超过 200 行总输出。
```
不加此约束，Explore 会把几百行真实配置倒回主线。

### 8d. 多轮询问合并
多个确认点合并成一次 `AskUserQuestion`（≤4 问）。分轮问等于在历史里多存 N 个来回。

### 8e. background 命令只 tail 结论
后台命令完成后，只取尾部输出或结论摘要，**禁止**读入完整输出文件（build/install 日志可达几十 KB）。

## 与既有规则

- 结构查询与禁委派细则：[codegraph.md](codegraph.md)。
- 探针 Carry 门禁：[agent-react.md](agent-react.md)。
- 主上下文静默 Carry：[agent-output-verbosity.md](agent-output-verbosity.md)。
<!-- BEGIN OPTIONAL:PROJECT_DELEGATION_NOTES -->
{{PROJECT_DELEGATION_NOTES}}
<!-- END OPTIONAL:PROJECT_DELEGATION_NOTES -->
