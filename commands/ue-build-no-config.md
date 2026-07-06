---
name: ue-build-no-config
description: 关闭 UE Editor → 编译 C++ → 重启 Editor（不跑 Python 配置）
---

# UE Build & Launch（跳过配置）

关 Editor → 全量 Build → 开 Editor，**不**执行配置脚本。

## 执行步骤

1. 读 [{{BUILD_WORKFLOW_DOC}}]({{BUILD_WORKFLOW_DOC}})
2. 运行：

```powershell
powershell -ExecutionPolicy Bypass -File "{{BUILD_LAUNCH_SCRIPT}}" -SkipConfig
```

默认走优雅关闭；只有 Editor 假死且你明确接受下次启动可能出现恢复包 / autosave
recovery dialog 时，才额外加 `-ForceKillEditor`。

3. 汇报 Build exit code；确认 Editor 已启动
4. 若后续需配置资产，提示用户运行 `/ue-python-config` 或 `/ue-launch-config`

## 适用场景

- 纯 C++ 改动，暂不需要 Editor 内 Python 配置
- 验证编译是否通过后再决定是否跑配置
