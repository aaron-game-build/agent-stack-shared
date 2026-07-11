---
name: ue-py-init
description: "首次配置 UE Python Agent 环境。创建知识库目录、初始化通用规则文档、验证 Editor 连接。触发关键词：初始化、init、首次配置、设置知识库、ue-py-init。"
disable-model-invocation: true
---

> 低频专项 skill：非主线工作流不触发，按需调用。

# 初始化 UE Python Agent

首次使用或新克隆仓库时运行一次。

<!-- BEGIN OPTIONAL:ALREADY_INITIALIZED_GUARD -->
{{SLOT:ALREADY_INITIALIZED_GUARD_TEXT}}
<!-- END OPTIONAL:ALREADY_INITIALIZED_GUARD -->

## 执行流程

### 1. 自动探测环境

Agent 自行完成以下探测，**不询问用户**（除非路径冲突）：

```bash
# 引擎路径：从 UnrealEditor 进程反推
powershell.exe -NoProfile -Command "(Get-Process UnrealEditor -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Path | Split-Path | Split-Path | Split-Path)"
# → 例如: C:\Program Files\Epic Games\UE_5.5\Engine

# 项目名：从 .uproject 文件名推断
# → 例如: MyProject.uproject → 项目名 MyProject

# 编译命令：自动拼接
# → <engine_root>/Build/BatchFiles/Build.bat <Project>Editor Win64 Development -Project="<project_root>/<Project>.uproject"
```

如果 Editor 未运行（进程探测失败），提示用户启动 Editor 后重试。

### 2. 分步确认配置

逐项展示探测结果，每项让用户确认或修改：

**① 引擎路径**
```
检测到引擎路径：C:\Program Files\Epic Games\UE_5.5\Engine
- 确认
- 手动指定其他路径
```

**② 项目名称**
```
从 .uproject 推断项目名：MyProject
- 确认
- 修改
```

**③ 知识库路径**
```
知识库文档放在哪里？
- {{KB_ROOT_FROM_PROJECT}}/（推荐）
- .claude/knowledge/
- 自定义路径
```

**④ 编译命令**（基于前面确认的引擎路径和项目名自动拼接，展示给用户看一眼）
```
编译命令：<engine_root>/Build/BatchFiles/Build.bat MyProjectEditor Win64 Development -Project="..."
- 确认
- 修改
```

### 3. 创建知识库目录结构

> **注**：以下目录结构与文件名为示例，按项目实际结构调整（已有 KB 的项目参考现有布局，勿覆盖）。

在确认的路径下创建：

```
{{KB_ROOT_FROM_PROJECT}}/
├── knowledge-base-entry.md  ← 必读路由
├── knowledge-base.md        ← 兼容壳 / 模板初始化入口
└── modules/                 ← 模块能力文档（初始为空）
```

### 4. 初始化知识库

将 `templates/knowledge-base.md` 作为兼容壳复制到用户指定的知识库路径，并创建空的 `modules/` 子目录：

```bash
cp templates/knowledge-base.md <知识库路径>/knowledge-base.md
mkdir <知识库路径>/modules/
```

模板已包含完整的初始结构（§1-§7），用户后续通过 evolve 流程逐步积累内容。

### 5. 写入配置文件

在**用户项目根目录**下创建 `.ue-py-config.json`（和 `.uproject` 同级）：

```json
{
  "project_name": "<项目名>",
  "knowledge_base": "{{KB_ROOT_FROM_PROJECT}}/knowledge-base-entry.md",
  "modules_dir": "{{KB_ROOT_FROM_PROJECT}}/modules/",
  "ue_python_script": "{{UE_PY_RUN_SCRIPT_PATH}}",
  "toolchain": {
    "readiness_token": "UE_REMOTE_OK",
    "readiness_ping": "import unreal; print('UE_REMOTE_OK')",
    "remote_exec_max_wait_seconds": 180,
    "remote_exec_poll_interval_seconds": 10
  },
  "platforms": {
    "windows": {
      "engine_root": "<探测到的引擎 Engine/ 绝对路径>",
      "project_root": "<项目根目录绝对路径>",
      "build_command": "<engine_root>/Build/BatchFiles/Build.bat <Project>Editor Win64 Development -Project=\"<project_root>/<Project>.uproject\" -waitmutex -NoLiveCoding"
    }
  }
}
```

> 其他 skill 启动时在当前工作目录向上查找 `.ue-py-config.json`（类似 `.gitignore` 的查找方式）。找不到时提示用户运行 `ue-py-init`。

### 6. 验证连接

```bash
UE_ENGINE_ROOT="<engine_root>" python <ue_python_script> "import unreal; print(unreal.SystemLibrary.get_engine_version())"
```

连接成功 → 初始化完成。
连接失败 → 引导用户检查 Remote Execution 设置。

<!-- BEGIN OPTIONAL:SYNC_WRAPPERS_STEP -->
### 7. 同步 agent-stack wrappers

```powershell
{{SYNC_WRAPPERS_COMMAND}}
```
<!-- END OPTIONAL:SYNC_WRAPPERS_STEP -->

## 完成输出

向用户确认：

```
✅ 初始化完成
  知识库位置：<路径>
  脚本位置：<路径>
  Editor 连接：<OK / 失败>
  编译命令：<已配置 / 未配置>

下一步：
  - 执行 UE 操作 → 使用 ue-py-run
  - 扩展 Python API → 使用 ue-py-extend
  - 沉淀经验 → 使用 ue-py-evolve
```
