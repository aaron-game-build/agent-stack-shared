---
name: ue-doc-audit
description: "全栈审查 Agent 文档：KB、rules、skills、AGENTS、静态门/验收路由。触发：doc audit、文档审查、里程碑签核前、规则漂移、ue-doc-audit。"
disable-model-invocation: true
---

# Agent 文档全栈审查

对 **操作 KB + rules/skills + 入口文档 + 验收路由** 做合规体检，输出可执行的修复清单。

## 何时调用

| 时机 | 必须？ |
|------|--------|
| {{SLOT:DOC_AUDIT_TRIGGERS}} |
| 每个 Gate / 里程碑收口 | 建议（必含剪枝 Pass + 生命周期检查） |
| 大改 rules 或 KB 后 | 建议 |
| 感觉 checklist 与 rules 不一致 | 建议 |
| 单次 `ue-py-evolve` 只改 1–2 处 KB | 否（只跑 `knowledge_graph_check --check` 即可） |

权威说明：[agent-doc-governance.md]({{KB_ROOT_FROM_SKILLS}}/modules/agent-doc-governance.md)

## 执行步骤

1. 读 `agent-doc-governance.md`（审查节奏 + 清单）
2. 在项目根运行：

```powershell
cd {{PROJECT_ROOT}}
python {{UE_PY_EVOLVE_SCRIPTS_DIR}}/agent_stack_check.py --check
python {{UE_PY_EVOLVE_SCRIPTS_DIR}}/agent_stack_check.py --check --strict
python {{UE_PY_EVOLVE_SCRIPTS_DIR}}/knowledge_graph_check.py --inventory
```

3. 将输出分为：**ERR 必修** / **WARN 建议** / **重复内容可收敛**（详述只保留 concepts/modules，rules/checklist 短重复）
   - `knowledge_graph_check.py --inventory` 会刷新 `concepts/inventory.generated.json`；Windows 路径分隔符 diff 是 generated drift，若 strict gate 通过则只报告，不手改 JSON。
4. 额外套一层 **Docs Quality Lens**（只做文档质量判断，不替代 machine gate）：
   - **结构**：章节层级、入口 / 兼容入口、权威落点是否清晰
   - **文案**：面向 Agent / 人类的语气是否明确，是否有内部术语堆叠
   - **引用**：链接是否可达，旧入口是否仍误导
   - **示例**：示例是否仍匹配当前命令 / workflow
   - **维护性**：是否有重复权威、长内容是否应下沉到 concepts/modules
   - 若发现 registry / route / manifest / schema 绑定问题，标记为 **需转交 governance gate**，不要用文案审查替代脚本检查
5. 向用户提交审查报告（日期、触发原因、exit code、待办表；必要时附 Docs Quality Lens）
6. **等待用户确认**后做最小 diff 修复（仅 Markdown / 脚本；**禁止**顺带改 C++、不改 Plan 文件）
7. 修复后重跑 `agent_stack_check.py --check --strict` 与 `knowledge_graph_check.py --check --strict`，汇报 0 error

## 与 evolve / retrospective 分工

| Skill | 职责 |
|-------|------|
| `ue-py-evolve` | 沉淀新坑；落库后 **KB strict**；里程碑时建议用户再跑 doc-audit |
| `ue-task-retrospective` | 任务复盘；若发现「规则缺失 / 全库漂移」→ Route 到 doc-audit 或 governance |
| **ue-doc-audit** | 全栈合规 + 周期节奏，不替代单次陷阱写入 |

## 剪枝 Pass（Prune Pass）

每次 doc-audit 里程碑，除查「该加什么」，必做一次反向检查：

- **三问**：
  1. 有 0 入站引用的孤儿文档吗？（`knowledge_graph_check --inventory` 可辅助）
  2. 有多个文档讲同一件事（重复治理）吗？可合并吗？
  3. 元治理文档改动节奏快过产品文档吗（治理倒置）？
- 每发现一处「应加」，同步问：有没有对应的「可删/可归档/可合并」？
- 给「加」配一个「删」的回路；孤儿、重复、冻结内容优先归档。

治理过重的解药不是更多治理，是给增长配背压。

### 生命周期检查（剪枝 Pass 的机械底座）

三问中的孤儿与重复由共享工具 `kb_lifecycle` 机械化，另加过期与废弃引用检测：

```powershell
cd {{PROJECT_ROOT}}
$env:PYTHONPATH = "agent-stack-shared/pylib"
python -m kb_lifecycle --kb-root {{KB_ROOT_FROM_PROJECT}}
```

检查项：metadata 完整性（条目须有 `status: active|deprecated` + `updated: YYYY-MM-DD`）、
stale（`updated` 超 180 天 → retirement candidate）、deprecated 条目仍被 active 文档引用、
合并候选（tags 高重合 / 同名跨 `modules/`/`concepts/`）、孤儿条目。

对报告逐项给出处置提案，与「加」的清单一起进第 5 步审查报告：

| 处置 | 动作 |
|------|------|
| **merge** | fold 进既有家族表/模块，删被并方，改齐入站链接 |
| **retire** | 直接删除（git 历史即归档，不建 archive 目录）；先确认无护栏仍依赖它 |
| **refresh** | 内容仍准确 → 只更新 `updated` 日期 |
| **automate** | 坑已被机器 validator 覆盖 → 压缩为一行 tag + validator 链接 |

工具是 advisory（WARN 不挂 CI）；处置一律走第 6 步用户确认，执行后重跑
markdown links / graph check 保证链接不烂。字段标准与节奏的权威说明在项目侧
[agent-doc-governance.md]({{KB_ROOT_FROM_SKILLS}}/modules/agent-doc-governance.md)。

## 禁止

- 用审查代替 L4/H 人工验收或改游戏逻辑
- 未经确认大改规则主路径（与 Plan Lock / Direction Lock 冲突）
- 在审查中删除项目已定的短反例（可收敛措辞，不可删约束）
- 用 Docs Quality Lens 代替 `agent_stack_check` / `knowledge_graph_check` 等机器门禁

<!-- BEGIN OPTIONAL:SYNC_WRAPPERS_STEP -->
## 同步 wrappers

改 canonical 后：

```powershell
{{SYNC_WRAPPERS_COMMAND}}
```
<!-- END OPTIONAL:SYNC_WRAPPERS_STEP -->

## 相关

- [tagging.md](../ue-py-evolve/tagging.md)
- [knowledge-base-entry.md]({{KB_ENTRY_PATH}})
- {{SLOT:DOC_AUDIT_RELATED_LINKS}}
