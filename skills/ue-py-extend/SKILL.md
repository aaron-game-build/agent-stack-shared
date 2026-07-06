---
name: ue-py-extend
description: "扩展 Agent 对 UE Editor 的控制能力。当现有 Python API 无法完成目标操作时，自动读源码、写 C++ UFUNCTION、编译验证、输出能力文档。当用户说'这个 Python 做不到'、'反射读不到'、'需要写 C++'、'帮我打通 XX 模块'、'扩展 Agent 能力'、ue-py-extend 时触发。也在用户尝试操作某个子系统反复失败（属性读不到、写不进去、报 protected）时主动建议使用。"
disable-model-invocation: true
---

> 低频专项 skill：非主线工作流不触发，按需调用。

# 扩展 Editor 能力

当 Python API 碰不到目标系统时，按标准流程自动扩展。

**何时用这个 skill**：当前 API 根本做不到你想做的事——属性不存在、接口没暴露、反射层碰不到。

**何时不用**：如果只是单次修改某个属性（知道怎么做但需要执行），用 `ue-py-run` 就够了。extend 是用在"能力缺口"的场景，不是日常操作工具。

## 前置依赖

- **ue-py-init**：必须先运行一次，生成 `.ue-py-config.json`
- **ue-py-run**：整个流程依赖它来执行 Python 验证代码
- **命令行编译环境**：需要能从命令行编译 UE 项目

## 开始前

1. 从当前目录向上查找 `.ue-py-config.json`，读取知识库路径和编译命令
   - 找不到？→ 提示用户先运行 `ue-py-init`
2. 读取 **knowledge-base-entry.md** — 必读路由、反射命名入口、已知陷阱分类
3. 读取 **[references/extension-spec.md](references/extension-spec.md)** — Phase 0→6 完整流程定义
4. 列出 **modules/** 目录，确认目标模块尚未覆盖
5. **汇报已读文档** — 向用户列出你读了哪些文件，确认没有遗漏

## Phase 流程概览

```
Phase 0: 定位模块边界 + 确认未被覆盖
Phase 1: 文档探索 Inventory（向用户汇报）
Phase 2: 阅读引擎源码 + 信息完整性审计 → 输出 _workdocs/<module>-audit.md
Phase 3: Editor 内实测（通过 ue-py-run 执行）— 覆盖反射层属性 + 审计标记的盲区
Phase 4: 写 C++ UFUNCTION 补能力缺口 → 编译 → 重新验证
Phase 5: 输出标准化能力文档到 knowledge/modules/<module>.md
Phase 6: 独立复审（用户在新会话中启动复审 Agent）
```

完整流程定义见 [references/extension-spec.md](references/extension-spec.md)。

## 编译流程

改完 C++ 后必须走完整流程（UE 不支持 plugin hot reload）：

```bash
# 1. 关闭 Editor
taskkill /F /IM UnrealEditor.exe

# 2. 编译
{{ENGINE_ROOT}}/Build/BatchFiles/Build.bat {{PROJECT_NAME}}Editor Win64 Development ^
    -Project="{{PROJECT_ROOT}}/{{PROJECT_NAME}}.uproject"

# 3. 重新启动 Editor
"{{ENGINE_ROOT}}/Binaries/Win64/UnrealEditor.exe" "{{PROJECT_ROOT}}/{{PROJECT_NAME}}.uproject"

# 4. 验证新 UFUNCTION 已暴露
python scripts/ue_python.py "import unreal; print(hasattr(unreal.YourLibrary, 'new_func'))"
```

> 首次使用时建议把编译命令保存为 `.bat` 脚本，或走 build/launch command 全量流程。

## 能力评估（两个维度）

评估在 Phase 0 初步做，Phase 2 读完源码后修正。详见 extension-spec。

**维度 A — API 难度**（碰到属性需要多少基础设施）：

| 层级 | 情况 | 做什么 |
|------|------|--------|
| A0 | 反射 API 能直接读写 | 纯 Python，不写 C++ |
| A1 | 需要绕过 protected 或手拼 struct 字符串 | 写薄 C++ 封装 |
| A2 | 类型错误会 silent fail | 类型安全 setter + validator |

**维度 B — 信息完整度**（Agent 通过当前可用通道能看到多少）：

| 层级 | 情况 | 意味着什么 |
|------|------|-----------|
| B0 | 反射覆盖完整 | 属性验证通过即可信赖 |
| B1 | 有已知盲区（PostLoad 注入、顺序敏感） | 需要额外处理白名单和顺序保持 |
| B2 | 反射只是子集（private 状态、编译产物、指针链拓扑） | 需要先暴露盲区，否则"看着对跑着不对" |

## 完成后

1. 能力文档保存到 `modules/<module>.md`（路径从 `.ue-py-config.json` 读取）
2. 手动调用 `ue-py-evolve` 沉淀过程中发现的通用陷阱
