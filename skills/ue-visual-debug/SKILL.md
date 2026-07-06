---

name: ue-visual-debug

description: Guides UE PIE debug visuals (range circles, traces, camera). Use when the user mentions debug circles, DrawDebug, decals, mesh debug actors, camera clipping, ground orientation, or says the circle is OK but needs smoother refresh—before replacing DrawDebug with mesh actors.

disable-model-invocation: true

---



# UE 可视化 Debug 工作流



> 配合 [ue-visual-debug-gate.mdc](../../rules/ue-visual-debug-gate.mdc)、[ue-agent-contracts.mdc](../../rules/ue-agent-contracts.mdc) §2。



## 何时读本 Skill



- Debug 圈、线、扇形、Sweep 可视化

- 「圈可以，只是叠影/帧率低/跟随不顺/抖」

- 相机挤到腰部、视口方向、地面圆方向错

- 考虑 Decal / StaticMesh / 新 Actor 显示范围



## 工作流（按序）



### 1. Confirm Accepted Direction



复述用户认可的现方案。若用户已认可 **DrawDebug 地面圆**，默认本轮只优化绘制策略/圆心/平面轴，**不**换 Mesh Actor。



### 2. Classify Rendering Primitive



| 选择 | 何时用 |

|------|--------|

| **DrawDebug** | MVP 范围圈、临时 Trace；首选 |

| **Decal** | 需要贴地、少叠影、有合适材质 |

| **专用透明环 Mesh** | 长期常驻、已做资产 |

| **Engine BasicShape Cylinder** | **不推荐** 代替调试圆 |



KB：[ue-visual-debug-primitives.md](../../../docs/ue-agent-knowledge/concepts/ue-visual-debug-primitives.md)



### 3. Risk Audit（Mesh/Material 时必填）



- 默认材质 / 棋盘格？

- Mesh 轴向与地面（圆柱默认 Z 轴为高度）？

- 挡相机、碰撞、阴影？

- Actor 生命周期与 Attach？



旋转：[ue-rotation-layers.md](../../../docs/ue-agent-knowledge/concepts/ue-rotation-layers.md)



### 4. Smallest Change First



| 用户抱怨 | 优先尝试 |

|----------|----------|

| 叠影 / 重影 / 3～4 条圆 | 按 KB **叠影三类根因**排查；终态：**每帧 Tick + `Duration=0` + 脚底圆心**（勿「略增 Duration、降 Tick」） |

| 圈「帧率低」 | 先查 `TickInterval` 是否故意限频（如 0.1s）；非游戏 FPS；用每帧 + `Duration=0` |

| 抖动 / 晕 | 圆心改**胶囊脚底** + `VInterp`；勿只加 Tick 或换 Mesh |

| 圆不在地上 | `DrawGroundRangeCircle`：`ForwardVector` + `RightVector` 作平面轴 |



<!-- BEGIN OPTIONAL:VISUAL_DEBUG_PROJECT_IMPL -->
{{VISUAL_DEBUG_PROJECT_IMPL}}
<!-- END OPTIONAL:VISUAL_DEBUG_PROJECT_IMPL -->



### 5. 叠影排查速查



1. `Duration >` 绘制间隔？→ **`Duration = 0`**

2. Duration 用了卡顿 `DeltaTime`？→ 勿 `max(Tick, DeltaTime)` 算寿命

3. 跑动拖影？→ **`Duration = 0`** + 脚底 + 插值



详情：[ue-visual-debug-primitives.md](../../../docs/ue-agent-knowledge/concepts/ue-visual-debug-primitives.md) §DrawDebug 叠影三类根因。



### 6. Observation Required



- PIE **Play**（非 Simulate）

- 用户或 Agent 目视：圆是否**贴地**、**水平**、**单圈**、**不挡视野**

- 截图或简短描述作为 Observe 证据



### 7. Rollback Rule



视觉与需求相反（竖盘、棋盘格墙、挡腰）→ **先回退错误提交**，再提新方案；禁止在错误 Mesh 上继续调参数。



## Micro-ReAct 模板（单步）



```markdown

**Reason**：假设 <…>；已认可方向 <DrawDebug 地面圆>

**Act**：<Duration=0 / 脚底圆心 / 平面轴 / …>

**Observe**：<PIE 截图描述 / 用户确认>

**Decide**：继续 | 回退 | 询问是否允许换 Decal/Mesh

```



## 禁止模式（反例）



- 用户说「圈可以，帧率低」→ 新建 `AMRAbilityRangeRingActor` + `BasicShapes/Cylinder` + `Pitch=90`

- 未穷尽 **`Duration=0` + 叠影三类** 前换 Component / Cylinder

- 未目视即写「Debug 已修复」

- 对默认材质设 `Color` 但未验证参数存在



## 关联



- 模块：[gas-combat-debug.md](../../../docs/ue-agent-knowledge/modules/gas-combat-debug.md) — §端到端：玩家脚下范围圈

- 概念：[ue-visual-debug-primitives.md](../../../docs/ue-agent-knowledge/concepts/ue-visual-debug-primitives.md)

- 复盘沉淀：[/ue-task-retrospective](../ue-task-retrospective/SKILL.md) + [/ue-py-evolve](../ue-py-evolve/SKILL.md)


