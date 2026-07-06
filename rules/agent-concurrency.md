# 多 Agent 并发协调

默认假设并发存在。`Editor`、`PIE`、`Build`、资产保存/移动/删改、共享脚本栈均为独占资源；只读调研与纯文档可并行。{{SLOT:CONCURRENCY_BACKGROUND_LINK}}

## 会前声明

可并行：只读调研、文档草案、不相交代码/文档（先声明 `claims`，避免公共接口）。Feature worktree 可并行，但 Editor/PIE/资产仍由 local/main 串行。

须串行：{{SLOT:CONCURRENCY_SERIAL_RESOURCES}}、`.uasset/.umap/DataAsset` 保存/移动/删改、Editor 开关、Build、Live Coding、Remote Exec、PIE Play/Stop/probe。Git index/commit/LFS 写入先 claim。

跨界协作先定 owner。

## 协调头

涉及多 Agent、共享资源或 Editor/PIE 时，Carry 前必须在当前会话发一段短协调头：

```markdown
并发协调：
- session: <id/title>
- task: <一句话目标>
- feature_id: <feature/current slice/none>
- worktree: local-main | codex-worktree | external-worktree
- mode: read-only | code | asset | editor | pie | build
- claims: <resource keys>
- exclusive: yes/no
- depends-on: <session/resource/none>
```

资源键统一用：`source:`、`python:`、`asset:/Game/...`、`map:/Game/...`、`script:`、`editor`、`pie`、`build`、`probe:<name>`。

## 冲突处理

1. 开工前读可见 sibling session 的最新协调头或完成总结。
2. 若两个 session claim 同一独占资源，后来的 session 停止 Carry，改做只读、计划、审阅或排队。
3. 不确定是否冲突时按冲突处理；不要赌 `Editor/PIE` 状态。
4. 结束或 `BLOCKED` 时释放 claim，说明 dirty 资源、未跑验证、是否需 integration owner。

## Packet 交接

长任务不能只靠聊天历史接力；跨 worktree / 阶段交付必须写外部状态锚点或 `integration packet`，含 `feature_id`、`changed_files`、`validation_ran`、`validation_not_run`、`needs_editor_pie`、`next_command`。缺字段时不得宣称"已可安全集成"。

## Editor / 进程约束

用户明确授予当前 session 独占，且无可见冲突 claim 时，才可关/启 `Editor`、执行 `Build`、保存声明范围内资产。

可见 `Unreal Editor` 默认先优雅关闭。若必须强杀，先说明"会触发 autosave recovery dialog / 可能丢失未保存内容"，并获用户批准。

只读 probe/audit/取证，优先用 `UnrealEditor-Cmd.exe -run=pythonscript` 或 editor-hosted runner；不要为恢复 `Remote Exec` 强杀用户正在用的 Editor。

## 禁止项

- 不知道其他 session 是否占用 `Editor/PIE` 时，擅自关 `Editor`、开/停 `PIE`、跑会改资产的脚本。
- 两个 Agent 同时移动、重命名、保存同一批资产或同一资产目录。
- 两个 Agent 同时修改{{SLOT:CONCURRENCY_SHARED_STACK_TARGETS}}。
- 把共享冲突留给最终 `git merge` 解决。
