---
name: ue-doc-audit
description: 全栈审查 Agent 文档（KB、rules、skills、AGENTS）；里程碑签核前建议
---

# UE Doc Audit

对 Agent 文档栈做合规体检。详见 [ue-doc-audit/SKILL.md](../skills/ue-doc-audit/SKILL.md)。

## 执行步骤

1. 读 [agent-doc-governance.md]({{KB_ROOT}}/modules/agent-doc-governance.md)
2. 在项目根运行：

```powershell
cd {{PROJECT_ROOT}}
python {{UE_PY_EVOLVE_SCRIPTS_DIR}}/agent_stack_check.py --check --strict
python {{UE_PY_EVOLVE_SCRIPTS_DIR}}/knowledge_graph_check.py --inventory
```

3. 按 SKILL 产出审查报告；用户确认后再修文档
4. 修复后重跑上述命令，exit 0 方可宣称审查通过

## 何时必须跑

- {{SLOT:DOC_AUDIT_TRIGGERS}}
- 大改 rules 或 KB 后

<!-- BEGIN OPTIONAL:SYNC_WRAPPERS_STEP -->
## 同步 wrappers

改 canonical 后：

```powershell
{{SYNC_WRAPPERS_COMMAND}}
```
<!-- END OPTIONAL:SYNC_WRAPPERS_STEP -->
