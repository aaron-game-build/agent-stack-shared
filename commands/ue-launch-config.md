---
name: ue-launch-config
description: 跳过编译，关闭并重启 UE Editor，然后运行 Python 配置脚本
---

# UE Launch & Config（跳过编译）

C++ **无变更**时：关 Editor → 开 Editor → 等 Remote Exec → 跑配置脚本。

## 执行步骤

1. 确认本轮**未改 C++**；若改了 C++ 请改用 `/ue-build-launch`
2. 运行：

```powershell
powershell -ExecutionPolicy Bypass -File "{{BUILD_LAUNCH_SCRIPT}}" -SkipBuild
```

默认走优雅关闭；只有 Editor 假死且你明确接受下次启动可能出现恢复包 / autosave
recovery dialog 时，才额外加 `-ForceKillEditor`。

3. 汇报：{{SLOT:BUILD_REPORT_FORMAT}}

## 适用场景

- 只改了 Blueprint / DataAsset / Python 配置脚本
- Editor 状态异常需重启后再跑配置

## 相关

- Editor 已开且只需重跑配置 → `/ue-python-config`
