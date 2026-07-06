---
name: ue-build-launch
description: 关闭 UE Editor → 编译 C++ → 重启 Editor → 运行配置脚本（完整流程）
---

# UE Build & Launch（完整流程）

执行 **关 Editor → Build → 开 Editor → Remote Exec → 跑配置脚本** 一条龙。

## 执行步骤

1. 读 [构建/启动工作流文档]({{BUILD_WORKFLOW_DOC}}) 与 `knowledge-base-entry.md` §5
2. 在项目根运行：

```powershell
powershell -ExecutionPolicy Bypass -File "{{BUILD_LAUNCH_SCRIPT}}"
```

默认走优雅关闭；只有 Editor 假死且你明确接受下次启动可能出现恢复包 / autosave
recovery dialog 时，才额外加 `-ForceKillEditor`。

3. 等待脚本完成；汇报：{{SLOT:BUILD_REPORT_FORMAT}}
4. **不得**在人工验收未过前写"完成 / 已修复"

## 适用场景

- 改了 C++（新 UCLASS、UPROPERTY 等）
- 需要 Editor 内重新加载 DLL 并跑资产配置

## 失败处理

| 现象 | 动作 |
|------|------|
| Build 失败 | 停止；汇报编译错误，不继续开 Editor |
| 180s 无 PING | 提示用户 Editor 可能仍在加载；建议稍后运行 `/ue-python-config` |
| Live Coding 占用 | 确认 Editor 已关闭后重跑 |
