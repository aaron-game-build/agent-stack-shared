<!-- CODEGRAPH_START -->
## CodeGraph

结构查询用 `codegraph_*`（AST 索引）；字面文本/日志用 grep。**勿**委派 Explore 替代 codegraph 结构查询。

| 意图 | 工具 |
|------|------|
| 定义 / 区域上下文 | `codegraph_search` / `codegraph_context` |
| 调用方 / 被调 | `codegraph_callers` / `codegraph_callees` |
| X→Y 路径 | `codegraph_trace`（一次返回全路径） |
| 改动影响 | `codegraph_impact` |
| 多符号源码 | `codegraph_explore`（一次 capped） |

**Pre-sync**：每批 exploration 前于 {{CODEGRAPH_PROJECT_PATH}} 根执行 `codegraph sync .`；MCP 传 `projectPath: {{CODEGRAPH_PROJECT_PATH}}`；同批只 sync 一次。`.codegraph/` 缺失 → `codegraph index . --force`。

**Poor-result**：空结果/`Variant_*` 污染 → **禁止** `Glob **/*` 广域 rg；逐级 retry：换符号名 → 换 `codegraph_context` → 缩小目录范围 → 最后才 grep。

**禁止**：grep 复核 codegraph 结果；`search`+`node` 链式（用 `context`/`explore`）；多轮 `codegraph_node` 循环。

Windows PATH fallback：`{{CODEGRAPH_PATH_FALLBACK}}`。

<!-- BEGIN OPTIONAL:CODEGRAPH_DETAIL_DOC -->
详述工具表与更多用法：{{CODEGRAPH_DETAIL_DOC}}。
<!-- END OPTIONAL:CODEGRAPH_DETAIL_DOC -->
<!-- CODEGRAPH_END -->
