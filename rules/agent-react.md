# REACT 工作流

**R**ead → **E**stimate → **A**udit → **C**arry → **T**est

L1–L4/H：{{SLOT:QUALITY_GATES_LINKS}}。

## 各阶段

- **Read**：{{SLOT:READ_ENTRYPOINTS}}；基线 {{SLOT:BASELINE_ADR_LINK}}。
- **Estimate**：目标/范围/验收；非平凡任务 Plan 或列 REACT 五步。
- **Audit**：{{SLOT:AUDIT_SCOPE_QUESTION}}？Editor/编译还是仓库？首次接触子系统？
- **Carry**：最小 diff；Plan 锁定后勿复述 REACT；遵守 [agent-contracts.mdc](agent-contracts.mdc)、[codegraph.mdc](codegraph.mdc)、[agent-output-verbosity.mdc](agent-output-verbosity.mdc)。
- **Test**：列实际检查结果；不得凭「应该可以」。

非平凡任务（多文件/C++/Editor/批量脚本/探针）：**必须 E+A 后再 C**。

长循环/可恢复任务：绑定 loop contract；L4/H 与并发门禁不得降级。

## 原子任务快速路径（反上下文漂移）

当请求映射到**单个已知命令/工具调用**（如"拉起 Editor"= 跑既定脚本、"push"= 一条 git 命令）时，跳过 REACT 铺陈：

1. **直通**：本回合的**第一个动作就是那个调用**，之前不读文件、不做计划、不反问、不加戏（主动性 prior 在原子任务上会"制造"相邻工作——抑制它，做完即停）。
2. **叙述不代替动作**：一旦发现自己在写"我这就 / 准备执行 / 接下来我会……"而指向的是**此刻就能调用**的工具——立刻改成调用本身。关于意图的文字≠推进。
3. **压缩恢复优先级**：若本回合是**上下文压缩后的续接**，先定位那个唯一的、用户在等的**挂起动作**并执行，**再**消费 summary 里的其他状态。挂起动作的优先级高于所有背景信息——summary 里 token 质量大的内容（里程碑/重构/状态）会盖过质量小的挂起动作，必须显式反制。

## Audit 三问

1. 验收标准？2. {{AUDIT_Q2_TARGET}} 哪些条目？3. Editor/编译还是仓库？4. {{SLOT:AUDIT_Q4_QUESTION}}

## Carry 微门禁

{{SLOT:CARRY_MICRO_GATES}}

<!-- BEGIN OPTIONAL:PROTECTED_CONTRACTS -->
Protected Contract：改到受保护依赖路径时，Carry 前声明影响半径；Test 前跑/请求 L3 证据包。详见 {{PROTECTED_CONTRACTS_REFS}}。
<!-- END OPTIONAL:PROTECTED_CONTRACTS -->

Escaped Bug：用户可见 bug/回归/L3-L4 不足/追问"为什么没拦住"时，不得只写"已修复"。按 [incident-to-guardrail-retrospective.md]({{KB_ROOT}}/modules/incident-to-guardrail-retrospective.md) 做五层分析，失败层路由到 rule/framework/probe/evidence/KB。

## Test / 禁止

- `ue_python.py` exit 0（Editor 任务）；C++ 关 Editor Build；PIE **Play** 不能省略。
- L4/H 需独占 editor 时标阻塞，不得静默跳过。
- 禁止：跳过 Test；L4 未过宣称完成；静态绿 token 代替人玩结论。
<!-- BEGIN OPTIONAL:PROJECT_TEST_NOTES -->
- {{PROJECT_TEST_NOTES}}
<!-- END OPTIONAL:PROJECT_TEST_NOTES -->

| 模式 | REACT |
|------|-------|
| Plan | E + A |
| Agent | R + C + T |
| Ask | 主要 R |
