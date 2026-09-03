# 03 · 多节点任务编排链路设计

## 1. 思路：能力模块化，链路组合化

把生成过程里反复出现的动作抽成**可复用能力模块**，再用上下文传递 + 条件分支组合成不同链路：

| 能力模块 | 做什么 | 复用于 |
| --- | --- | --- |
| 需求理解 | 把零散输入归一成结构化需求，标注缺失项 | A1 |
| 知识检索 | 双路召回 + 过滤 + 重排（见 [02](02-rag-design.md)） | A1、A2、A3、R1 |
| 方案生成 | 基于需求 + 检索结果产出结构化方案 | A1、A2、A4 |
| 资源规划 | 给方案里每个任务补负责人/时间/预算 | A2 |
| 成果输出 | 把方案渲染成指定 Schema 的文档/清单 | A3、R2 |
| 复盘分析 | 校验数据口径，区分事实/推断/待确认 | R1 |

## 2. 六个 Dify 应用

| 编号 | 应用 | 类型 | 输入变量 | 组成的能力模块 | 输出（写入 `projects` 列） |
| --- | --- | --- | --- | --- | --- |
| A1 | SOP 大纲生成 | Workflow | `activity_name, activity_type, background, date, target, budget, department` | 需求理解 → 知识检索 → 方案生成 | `a1_data` |
| A2 | 执行主表生成 | Workflow | `sop_outline, project_info` | 知识检索（合规） → 方案生成 → 资源规划 | `a2_data` |
| A3 | 配套成果生成 | Workflow | `task_table, project_info, asset_type` | 知识检索（规范） → 成果输出 | `a3_data` |
| A4 | AI 修改助手 | **Chatflow** | `project_context`（对话） | 方案生成（增量 diff） | `versions` 追加草稿 |
| R1 | 活动复盘分析 | Workflow | `event_data, task_table, feedback_data` | 复盘分析 | `r1_data` |
| R2 | 复盘报告生成 | Workflow | `r1_analysis, project_info` | 成果输出 | `r2_data` |

**为什么 A4 用 Chatflow 而其它用 Workflow**：
A1–A3、R1、R2 是"一次输入 → 一次结构化输出"的批处理，Workflow 的 DAG 更合适；
A4 是多轮对话式修改，需要会话记忆和澄清追问，用 Chatflow。

## 3. 上下文如何在节点间传递

链路不是简单串行，靠 `projects` 表的 JSON 列做"共享黑板"：

```
A1 ──写──> a1_data ──读──> A2 ──写──> a2_data ──读──> A3
                                  │                    │
                                  └── project_info ────┘  (基本信息全程只读传递)

R1 ──写──> r1_data ──[人工确认口径]──> R2 ──写──> r2_data
```

- 每个应用只依赖**上游已确认的产物**，不直接调用上游应用
- 前端负责编排：读上游列 → 组装 `inputs` → 调后端代理 → 写当前列
- 条件分支：如"执行主表未确认" → A3 入口置灰（`index.html` 阶段门槛逻辑）

## 4. 后端代理协议

后端 `main.py` 对 6 个应用提供**统一转发协议**，不感知业务语义：

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/dify/workflow/<app_id>` | POST | 阻塞式调用 Dify `/workflows/run` |
| `/api/dify/workflow-stream/<app_id>` | POST | SSE 流式转发 |
| `/api/dify/chat/<app_id>` | POST | 阻塞式调用 Dify `/chat-messages`（A4） |
| `/api/dify/chat-stream/<app_id>` | POST | SSE 流式转发（A4） |

`<app_id>` ∈ `A1 A2 A3 A4 R1 R2`，后端用 `APP_KEY_MAP` 查出对应 Key 注入 `Authorization` 头。

请求体：

```json
{
  "inputs": { "...": "各应用的输入变量" },
  "user": "sop-platform",
  "project_id": 12,
  "query": "仅 chat 用",
  "conversation_id": "仅 chat 多轮用"
}
```

每次调用无论成败都写 `dify_calls` 表：`app_id / call_type / input_data(截断2k) / output_data(截断5k) / duration_ms / status / error_msg / project_id`。
这张表是链路可观测性的唯一数据源，供管理后台「Dify 调用记录」页与 `/api/stats` 使用。

## 5. 已知可观测性缺口

- 只记录首尾，Dify Workflow 内部节点耗时不可见（依赖 Dify 自身面板）
- 流式调用只记 `[stream]` 占位，不留全文
- 无 trace id 贯穿前端→后端→Dify
