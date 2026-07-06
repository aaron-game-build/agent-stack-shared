---
name: ue-live-coding
description: Editor 已开时触发 Live Coding（Ctrl+Alt+F11）；仅适用于纯 .cpp 函数体变更
---

# UE Live Coding（热重载）

**默认仍应关 Editor 全量 Build**（`/ue-build-launch` / `/ue-build-no-config`）。本命令仅用于 **纯 .cpp 函数体** 小改且需快速验证时。

## 执行前 Read

1. 确认本轮 **未改** `.h` 成员、UPROPERTY、UCLASS、UFUNCTION、Build.cs
2. {{SLOT:LIVE_CODING_PRE_READ_LINK}}

## 执行步骤

1. 确认 **UnrealEditor 已启动**且项目窗口在前台
2. 发送 Live Coding 快捷键：

```powershell
$ws = New-Object -ComObject WScript.Shell
if (-not $ws.AppActivate('{{PROJECT_WINDOW_TITLE}}')) {
    Write-Error 'Could not activate {{PROJECT_WINDOW_TITLE}} Editor window'
    exit 1
}
Start-Sleep -Milliseconds 500
$ws.SendKeys('^%{F11}')
Write-Host 'Sent Ctrl+Alt+F11 (Live Coding). Check Output Log for Live coding succeeded.'
```

3. 用户在 Output Log 确认 **「Live coding succeeded」**；若失败或行为不变 → 关 Editor 跑 `/ue-build-no-config`

## 禁止

- 新增 UCLASS / USTRUCT / UPROPERTY 后仅 Live Coding
- 行为不变时反复 SendKeys — 先查是否改过 `.h`

## 相关

- {{SLOT:RELATED_RUNTIME_DEBUG_LINKS}}
