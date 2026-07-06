---
name: ue-py-run
description: "在运行中的 UE Editor 内远程执行 Python 代码。当用户需要查询 Editor 状态、操控资产、控制 PIE、自动化编辑器操作时使用。触发关键词：UE 编辑器自动化、Unreal Python、编辑器脚本、场景操控、资产操作、PIE 控制、ue-py-run，或任何暗示需要在 UE 编辑器进程内执行代码的请求。"
disable-model-invocation: true
---

# UE Python 远程执行

通过 Remote Execution 协议向运行中的 UE Editor 发送 Python 代码并取回结果。基于 UE 内置的 Remote Execution 协议（UDP 发现 + TCP 执行），脚本约 100 行。

## 开始前

1. 从当前目录向上查找 `.ue-py-config.json`，读取配置（`engine_root`、知识库路径、脚本路径）
   - 找不到？→ 提示用户先运行 `ue-py-init` 完成首次配置
2. 读取 **[knowledge-base-entry.md]({{KB_ENTRY_PATH}})**（通用规则、命名约定、已知陷阱 §5）
3. 如果任务涉及特定模块，读取 **modules/\<module\>.md**（如存在）
4. 验证连接（用配置中的 `engine_root` 调用脚本）

> 跳过第 2 步直接写代码会踩已知陷阱（反射命名写错、路径格式搞混）。

## 引擎路径

脚本通过 `UE_ENGINE_ROOT` 环境变量定位引擎。路径来源（按优先级）：

1. **读配置**：`.ue-py-config.json` 中的 `engine_root` 字段（init 时已写入）
2. **进程探测**（兜底）：配置缺失时实时探测

```bash
# 兜底探测命令
powershell.exe -NoProfile -Command "(Get-Process UnrealEditor -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Path | Split-Path | Split-Path | Split-Path)"
```

## 调用方式

```bash
# 执行代码字符串（UE_ENGINE_ROOT 由 Agent 在调用前通过进程探测获得）
UE_ENGINE_ROOT="<engine_path>" python scripts/ue_python.py "import unreal; print(...)"

# 自定义超时（默认 6 秒）
UE_ENGINE_ROOT="<engine_path>" python scripts/ue_python.py "import unreal; print('hello')" 15
```

退出码：`0` = 成功，`1` = Python 执行错误（返回 traceback），`2` = 连接失败。

## 常用示例

```python
# 查询场景中所有 Actor
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
for a in actors:
    print(f"{a.get_actor_label()} at {a.get_actor_location()}")
```

```python
# 修改资产属性
import unreal
asset = unreal.load_asset('/Game/Data/DT_Weapons')
asset.set_editor_property('some_property', new_value)
```

```python
# 启动 PIE
import unreal
subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
subsystem.editor_play_simulate()
```

## 注意事项

- 代码顶部必须 `import unreal`
- 用 `print()` 输出——stdout 会被捕获并返回给调用方
- 出错时返回完整的 Python traceback（含行号和调用栈）
- 编辑器必须在主窗口（不能处于模态对话框状态）
- 尽量把多个操作写在一段脚本里一次发送，减少往返通信

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 进程探测无输出 | Editor 未运行 | 启动 Editor 后重试 |
| Exit code 2 + "cannot find remote_execution.py" | 传入的路径有误 | 确认路径末尾是 `Engine/`，且含 `Plugins/.../PythonScriptPlugin` |
| Exit code 2 + "No UE Editor found" | Remote Execution 未开启 | Editor Preferences → Python → Remote Execution |
| Exit code 1 + traceback | Python 代码执行错误 | 阅读 traceback，修正代码 |
| 超时无响应 | Editor 处于模态对话框 | 关闭对话框后重试 |

## 完成后

如果执行中发现了知识库未覆盖的陷阱或新模式，手动调用 `ue-py-evolve` 沉淀经验。
