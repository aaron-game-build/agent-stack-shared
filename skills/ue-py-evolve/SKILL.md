---
name: ue-py-evolve
description: "回顾并改进知识体系文档。在 ue-py-run 或 ue-py-extend 完成后手动调用，将新发现的陷阱、规则、模式沉淀到知识库。触发关键词：文档改进、知识沉淀、更新知识库、evolve、ue-py-evolve。"
disable-model-invocation: true
---

# 知识自进化

根据刚才的工作历史，回顾遇到的问题，改进知识库文档。

## 何时调用

- `ue-py-run` 执行中踩了知识库里没写的坑 → 调用 evolve 补进去
- `ue-py-extend` 打通了新模块 → 调用 evolve 检查文档质量
- 发现知识库里的内容过时或错误 → 调用 evolve 修正
- **REACT Test** 发现 validation-checklist 未覆盖的新坑 → 建议 evolve 沉淀

> 这是手动触发的 skill，不会自动运行。

## 知识库位置

从 `.ue-py-config.json` 读取。首次使用前必须先运行 `ue-py-init`。

典型结构：

```
{{KB_ROOT_FROM_PROJECT}}/
├── knowledge-base-entry.md  必读路由 + §5 分类入口
├── knowledge-base.md        兼容壳，指向 entry
├── concepts/                概念层（标签 + 简单例子 + 双向链接）
│   ├── index.md
│   └── *.md
└── modules/
    ├── development-quality-gates.md
    └── ...
```

标签与概念页规范见 [tagging.md](tagging.md)。

## 执行方式

1. 从当前目录向上查找 `.ue-py-config.json`，读取知识库路径
   - 找不到？→ 提示用户先运行 `ue-py-init`
2. 读取 `knowledge-base-entry.md` 与 `concepts/index.md`（若存在）
3. 列出 `modules/`、`concepts/`，读取与本次工作相关的文档
4. **汇报已读文档** — 向用户列出你读了哪些文件
5. 回顾上下文历史，对照知识库找出可改进的点
6. 按文件分组列出建议：**改什么、为什么、改成什么**（含推荐 `tags` / `related_concepts`）
7. 等待用户确认后写入（用户说「直接改知识库」可跳过确认，仍须汇报改动）
8. **落库后**运行知识图谱校验（见下「图谱维护」）
9. **自动评估并执行 Phase B**（见下）：用户**不需要**主动说「处理 PhaseB」

## Phase B：代码晋升（自动评估，条件满足则执行）

> 与 `ue-task-retrospective` 配合：retrospective 在候选中标注 Phase B 建议；evolve **自行评估**是否纳入本次执行。

**不要**在每次 evolve 时无差别拆分全部 `Content/Python` 脚本。只晋升满足门禁的重复/稳定逻辑。

### 何时执行 Phase B

**Phase A 已确认落库**（或用户明确要求只改文档时跳过 Phase B），且用户**未明确排除** Phase B（如「只改 KB、不动 Python」），且满足以下**任一**条件时，**默认纳入本次执行范围**：

1. 同一 UE Python 操作在 ≥2 个脚本重复
2. 本次 KB 沉淀涉及 `op:` / `script:` / `{{PY_OPS_PACKAGE}}` 落点或 `{{PY_OPS_ARCHITECTURE_DOC}}`
3. `ue-task-retrospective` 候选标明 Phase B / `{{PY_OPS_PACKAGE}}` 晋升
4. 现有 `Content/Python` 脚本含应下沉的临时逻辑、重复资产操作、未进 `reload.py` 的 workflow 链
5. 对应 `pitfall:` 已写入 KB 且实现模式稳定

### 执行要求

- **非平凡** Python 改动（多文件、`workflows/`/`audits/` 行为变化）：在回复或 Plan 中**明示** Phase B 影响范围（改了哪些 `{{PY_OPS_PACKAGE}}`、哪些 wrapper）；可静默做小函数提取，但不得隐瞒大范围重构
- 用户**无需**单独触发「Phase B」口令
- 完成后：更新 `{{PY_OPS_ARCHITECTURE_DOC}}` 索引；`knowledge_graph_check.py --check --strict`（Phase A 已跑则再跑亦可）
- **运行时回归（必做）**：图谱校验**不能**代替 Python 可执行性。至少满足其一：
  - 对受影响入口跑 `ue_python.py` 执行相关 wrapper（如对应 audit），**exit 0**；或
  - Editor 未开时：在项目根对变更模块做 `python -c "import sys; sys.path.insert(0,'Content/Python'); import {{PY_OPS_PACKAGE}}.<module>"` 无 ImportError
  - 在回复中列出**实际跑过的命令**与 exit code

### 禁止晋升

- `Content/Python/maintenance/`、一次性 cleanup
- 历史探测/修复脚本（如一次性路径修补）
- 仅本次任务有效的路径或探针

### 晋升动作清单

1. 提取函数到 `Content/Python/{{PY_OPS_PACKAGE}}/<domain>.py`，补 docstring metadata（见 [tagging.md](tagging.md) `python_op`）
2. `workflows/<name>.py` 只组合 `{{PY_OPS_PACKAGE}}`；根目录保留薄 wrapper（`sys.path` + `main()`）
3. 更新 [{{PY_OPS_ARCHITECTURE_DOC}}]({{KB_ROOT_FROM_SKILLS}}/{{PY_OPS_ARCHITECTURE_DOC}}) 索引表
4. concept/module 双向链接补 `{{PY_OPS_PACKAGE}}/...`
5. 跑 `knowledge_graph_check.py --check --strict`

### 与 retrospective 分工

| Skill | 职责 |
|-------|------|
| `ue-task-retrospective` | 候选知识 + **链路完整性** + Phase B 建议 |
| `ue-py-evolve` Phase A | 写 KB + 图谱校验 |
| `ue-py-evolve` Phase B | 满足门禁时**自动**晋升 `{{PY_OPS_PACKAGE}}`（用户未排除则执行） |

## 图谱维护（写入时必做）

用户确认写入后，除改 `knowledge-base-entry.md` / `concepts/` / `modules/` 外：

1. 若涉及稳定概念 → 更新或新建 `concepts/<slug>.md`（用 [tagging.md](tagging.md) 模板）
2. 更新 `concepts/index.md` 表格行
3. 在案例章节下补相关概念链接；概念页补「关联案例」
4. 模块 frontmatter：`tags`、`related_concepts` 与正文一致
5. 运行校验：

```powershell
python "{{UE_PY_EVOLVE_SCRIPTS_DIR}}/knowledge_graph_check.py" --check --strict
python "{{UE_PY_EVOLVE_SCRIPTS_DIR}}/knowledge_graph_check.py" --inventory
```

**Phase 里程碑 / 大改 rules+KB 后**：另跑全栈审查（见 [agent-doc-governance.md]({{KB_ROOT_FROM_SKILLS}}/modules/agent-doc-governance.md)）：

```powershell
python "{{UE_PY_EVOLVE_SCRIPTS_DIR}}/agent_stack_check.py" --check --strict
```

或用户触发 `/ue-doc-audit`。

校验路径由 `.ue-py-config.json` 中 `knowledge_base` 字段自动推断知识库根目录；也可用 `--root` 指定。

失败则修复断链/孤立概念，再向用户汇报校验结果。常见报错速查见 [tagging.md](tagging.md) §校验常见失败。

## 落盘前检查（写入 KB 和/或 Phase B 后）

与 [ue-task-retrospective](../ue-task-retrospective/SKILL.md) 对齐，evolve 收尾前确认：

- [ ] 无遗留调试 C++ / 临时 `Build.cs` 路径（本次若做过 Debug 模式）
- [ ] 改过 C++ 时编译通过（防 Agent 写 `.cpp` 后 `C4335` Mac 行尾 — Windows 须 **CRLF**）
- [ ] Phase B 已做**运行时回归**（见上，非仅 graph check）
- [ ] `related_modules` / `related_concepts` 仅指向 `{{KB_ROOT_FROM_PROJECT}}` 内文件；`Docs/plans/` 或等价规划目录链到正文「相关文档」

## 写入 C++ / 多文件时注意

- 在 Windows 仓库编辑 `.cpp` / `.h` 后，若 `Build.bat` 报 **`error C4335: 检测到 Mac 文件格式`**：将文件行尾改为 CRLF 再编译（`knowledge-base-entry.md` §5 已有入口）。
- 优先小步 diff；大范围 C++ 调试插桩不应随 evolve 落库。

## 初始化（首次使用）

如果知识库目录下文件为空或刚从模板创建：

1. 回顾当前会话的执行记录
2. 提取遇到的所有错误和解决方式
3. 将高频入口写入 `knowledge-base-entry.md` §5，详述放 concepts/modules
4. 如果打通了新模块，创建 `modules/<module>.md`

## 改进原则

- **只沉淀通用知识**——不写入当前任务的具体资产名、统计数、一次性脚本路径
- **遇到 2 次以上的问题才沉淀**——或者 1 次就导致严重后果的陷阱
- **保持精炼**——上下文填到 40% 以上 Agent 注意力开始分散，宁可少写几条高频的，不要堆一堆低频的
- **反问判据**：这段删掉后，下一个 Agent 会不会走弯路？不会 → 不写

## 输出格式

建议以如下格式提交改进：

```markdown
## 建议修改

### knowledge-base-entry.md §5 已知陷阱

**新增陷阱 N：**
- 现象：<Agent 遇到了什么>
- 原因：<为什么会这样>
- 解决：<怎么避免或修复>

### modules/<module>.md

**修改验收清单第 X 行：**
- 原内容：...
- 改为：...
- 原因：<实测发现>

### concepts/<slug>.md（新建或更新）

- 新增「常见误判」一行
- tags: `concept:...`, `pitfall:...`
- 关联案例链到 modules

## Phase B（若执行）

- 改动文件列表：`{{PY_OPS_PACKAGE}}/...`、`workflows/...`、wrapper
- 运行时回归：`<命令>` → exit code
- `{{PY_OPS_ARCHITECTURE_DOC}}` 索引已更新
```

## 附加资源

- [tagging.md](tagging.md) — 标签前缀、概念页模板、禁止标签化
- `scripts/knowledge_graph_check.py` — `--check` / `--print-tags` / `--inventory`
