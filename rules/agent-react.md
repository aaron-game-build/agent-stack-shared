# REACT 工作流

**R**ead → **E**stimate → **A**udit → **C**arry → **T**est

L1–L4/H：{{SLOT:QUALITY_GATES_LINKS}}。

## 各阶段

- **Read**：{{SLOT:READ_ENTRYPOINTS}}；基线 {{SLOT:BASELINE_ADR_LINK}}。
- **Estimate**：目标/范围/验收；非平凡任务 Plan 或列 REACT 五步。
- **Audit**：{{SLOT:AUDIT_SCOPE_QUESTION}}？Editor/编译还是仓库？首次接触子系统？
- **Carry**：最小 diff；Plan 锁定后勿复述 REACT；遵守 [agent-contracts.md](agent-contracts.md)、[codegraph.md](codegraph.md)、[agent-output-verbosity.md](agent-output-verbosity.md)。
- **Test**：列实际检查结果；不得凭「应该可以」。

非平凡任务（多文件/C++/Editor/批量脚本/探针）：**必须 E+A 后再 C**。

长循环/可恢复任务：绑定 loop contract；L4/H 与并发门禁不得降级。

## Audit 三问

1. 验收标准？2. {{AUDIT_Q2_TARGET}} 哪些条目？3. Editor/编译还是仓库？4. {{SLOT:AUDIT_Q4_QUESTION}}

## Carry 微门禁

{{SLOT:CARRY_MICRO_GATES}}

<!-- BEGIN OPTIONAL:PROTECTED_CONTRACTS -->
Protected Contract：改到受保护依赖路径时，Carry 前声明影响半径；Test 前跑/请求 L3 证据包。详见 {{PROTECTED_CONTRACTS_REFS}}。
<!-- END OPTIONAL:PROTECTED_CONTRACTS -->

Escaped Bug：用户可见 bug/回归/L3-L4 不足/追问"为什么没拦住"时，不得只写"已修复"。按 [incident-to-guardrail-retrospective.md]({{KB_ROOT}}/modules/incident-to-guardrail-retrospective.md) 做五层分析。

## Test / 禁止

- `ue_python.py` exit 0（Editor 任务）；C++ 关 Editor Build；PIE **Play** 不能省略。
- L4/H 需独占 editor 时标阻塞，不得静默跳过。
- 禁止：跳过 Test；L4 未过宣称完成；静态绿 token 代替人玩结论。

| 模式 | REACT |
|------|-------|
| Plan | E + A |
| Agent | R + C + T |
| Ask | 主要 R |
