# Agent Contracts（Plan + Direction）

与 [agent-react.mdc](agent-react.mdc) 互补：管**已确认 Plan** 与**口头已认可实现方向**。

## §1 Plan Lock

**启用**：{{SLOT:PLAN_LOCK_SCOPE}}。**不启用**：纯问答、单行修复；用户说「先试试 / 不用 Plan」。

**锁定时机**：用户确认 Plan / AskQuestion 已选 / 「按这个方案做」「开始实施」。锁定：目标、主路径、验收标准、阻塞步骤。

### Carry 禁止（须 BLOCKED）

| 类别 | 禁止 |
|------|------|
| 主路径 | 换{{SLOT:MAIN_PATH_DOMAIN_EXAMPLES}}（未经用户确认） |
| 已认可方向 | 用户认可 A、只抱怨 B → 擅自换 C{{SLOT:DIRECTION_SWITCH_EXAMPLES}} |
| 跳过/降级 | 阻塞步骤 `skipped`；Audit 代替 PIE L4；删能力换安静 |
| 资产删改门禁 | Plan 写明 **用户 L4 目视** 的 `git rm` / 大批量资产变更：L3 绿也须在用户 PIE 确认前 **commit/push** 删包类变更；不得以「磁盘仍有文件」代替 L4 |

**允许**：Plan 已列 fallback；同一目标等价实现；编译/CRLF 工程修复；Plan 下一步逐步实施。

## §2 Accepted Direction

用户说「可以」「圈可以」「沿原来的」「只是优化 X」等 → **方向已认可**（除非随后推翻）。

**允许**：调参；修 bug；Plan fallback。

**禁止**：换激活路径未说明；错误方案上继续叠复杂度；静默扩大范围。

**调试假设被否决时**：为验证假设而改动的**产品代码**（非插桩）须在假设被否决后**立即撤销**。优先用插桩 / L3 audit / remote query 验证。

**Carry 前声明**（有已认可方向时）：

> **已认可方向**：\<当前方向\>；本轮仅做 \<局部改动\>，不切换到 \<拟换路径\>。

**Goal 标准变更**：若用户中途收窄或放宽完成标准，Agent 必须显式复述旧标准、新标准和残余验收；可以按新标准完成，但不得把旧标准静默写成已完成。

<!-- BEGIN OPTIONAL:PROJECT_DIRECTION_LOCKS -->
**项目方向锁**（已认可的项目级默认方案，未经用户确认不得改换）：

{{PROJECT_DIRECTION_LOCKS}}
<!-- END OPTIONAL:PROJECT_DIRECTION_LOCKS -->

## §3 BLOCKED 协议

满足任一即 BLOCKED（同一绕路最多 2 次后必须停）：Editor 失败且无备选；同一假设修 2 次仍不满足验收；Plan 前提错误且未覆盖。

```markdown
## BLOCKED — 需你决定

**Plan 步骤**：<第 N 步>
**验收项**：<哪条无法满足>
**阻塞现象**：<错误 / 日志证据>
**已尝试**：<最多 2 次>
**不能擅自**：<捷径及为何不满足 Plan>

**选项**：A. 继续原 Plan | B. 修订 Plan | C. 暂停
```

未收到选择前：不切换主路径、不写「已实施 / 已修复」。
