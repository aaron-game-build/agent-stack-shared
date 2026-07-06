---
name: ue-python-config
description: Editor 已运行时，通过 Remote Execution 执行 Python 配置脚本
---

# UE Run Python Config

Editor **已开**且 Remote Execution 已启用时，单独跑项目配置脚本。

## 执行步骤

1. 读 {{SLOT:PYTHON_CONFIG_BOUNDARY_DOC}} 了解自动化边界
2. 从 [`.ue-py-config.json`](../../.ue-py-config.json) 读取 `platforms.windows.engine_root` 与 `ue_python_script`；readiness token 见 `toolchain.readiness_token`（默认 `UE_REMOTE_OK`）
3. 先 ping Editor：

```powershell
$cfg = Get-Content ".ue-py-config.json" -Encoding UTF8 | ConvertFrom-Json
$env:UE_ENGINE_ROOT = $cfg.platforms.windows.engine_root
$env:PYTHONIOENCODING = "utf-8"
$uePy = Join-Path $PWD $cfg.ue_python_script
python $uePy $cfg.toolchain.readiness_ping
```

4. ping 成功后执行配置（**推荐 `-f` 文件模式，禁止 inline 大段 Python**）：

```powershell
python $uePy -f (Join-Path $PWD "{{CONFIG_SCRIPT}}")
```

5. 汇报 {{SLOT:BUILD_REPORT_FORMAT}}；未完成的必做项不得宣称验收通过

## 前置条件

- Editor 已启动
- `Project Settings → Plugins → Python → Enable Remote Execution Script` 已勾选
- 若 ping 失败（exit 2），提示用户先开 Editor 或运行 `/ue-launch-config`

## 路径说明

引擎路径、runner 脚本、readiness token 均以 [`.ue-py-config.json`](../../.ue-py-config.json) 为单一真相源；勿硬编码历史遗留路径。

## 禁止

- inline 大段 Python — 一律 `-f` 脚本文件
