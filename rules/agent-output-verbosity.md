# Agent 输出 Verbosity

降低多轮 Agent 任务的 narration token；与 [agent-contracts.md](agent-contracts.md) 互补，**不压缩** Plan Lock / BLOCKED / Direction Lock。

## 级别

| 级别 | 触发 | Carry 中 |
|------|------|----------|
| **L0** | 用户说「静默 / 省 token / 少说话」 | 仅必须说话项 + 完成总结 |
| **L1（默认）** | 未指定 | Carry **静默**；每完成一个**已锁定 Plan 步骤**一行；完成时短模板 |
| **L2** | 用户说「详细 / 调试」 | 允许 REACT 逐步 narration |

Plan 模式仍输出完整 Plan；本规则主要约束 **Agent 执行轮**。

## 模式分界

| 模式 | 输出 |
|------|------|
| **Ask / Plan 评审** | 可完整分析、引用代码；用户未要求执行时不强行 L1 |
| **Agent Carry**（Plan 已锁定或用户说「直接做」） | L1：**禁止**再写 REACT 五步复述、Audit 三问全文、Read 清单 |

Direction Lock 仅 **一行**（已认可方向 + 本轮局部范围）；不得接段落式实施计划。

## 必须说话（L0/L1/L2）

- Plan 未锁定前的 Estimate / Audit
- **BLOCKED** 协议全文（见 agent-contracts.md §3）
- 拟偏离已认可 Direction 或 Plan 主路径
- 需用户 L4 目视或删改资产的门禁
- 同类环境操作（Build / 启 Editor / Remote 轮询）**连续失败 ≥2 次** — 合并为一条阻塞说明，勿每 retry 一段

## 禁止（L0/L1）

- **工具回声**：「我先读 xxx…」「接下来 grep…」「现在进入 C++ 验证…」
- **英文 thinking 泄漏**：`**Planning …**` / `**Considering …**` 等英文链式思考段落（对用户无增量，高 token）
- Carry 中复述 Read/Audit 已覆盖内容
- 每个 `ApplyPatch` / 单文件改动单独预告
- 完成时长篇散文复盘

**静默批次**：并行 `Read`/`grep`/MCP/CodeGraph、`sync`、编译、探针、启 Editor — 整批零 narration；仅在结论变化或失败时说话。

Plan 步骤一行格式：`✓ <步骤名> — <一句结果>`（无步骤则跳过）。

## 完成短模板（L0/L1）

```markdown
## 完成
- 改动：<文件/行为>
- 验证：<L1–L4 实际项与结果>
- 未验 / 风险：<若有>
```

上限约 **15 行**；代码引用仅关键 1–2 处。
