# 05 · 后端 API 参考

后端 `main.py` 提供的全部 HTTP 接口。基址为服务根，例如 `http://localhost:8000`。
所有响应均为 JSON（流式接口除外）。

## 鉴权

- 标 🔒 的接口需要**管理员认证**：HTTP Basic（用户名任意，密码 = `ADMIN_TOKEN`），或请求头 `X-Admin-Token: <ADMIN_TOKEN>`。
- 未配置 `ADMIN_TOKEN` 时为**开发模式**：全部放行，响应头带 `X-Auth-Warning`。
- 未通过认证的 🔒 接口返回 `401` + `WWW-Authenticate: Basic`。

## 页面

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 业务工作台 `static/index.html` |
| `/admin` 🔒 | GET | 运营管理后台 `static/admin.html` |
| `/static/<file>` | GET | 静态资源 |
| `/healthz` | GET | 健康检查，返回 `{"ok": true}` |

## 1. API 配置管理

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/config` | GET | 读取平台地址与 6 个 Key 的状态（`configured` / `masked` / `source` / `editable`）。加 `?reveal=1` 且通过管理员认证时才额外返回 `raw` 明文 |
| `/api/config` 🔒 | PUT | 更新配置。Body: `{base_url, key_a1..key_r2}`。回传掩码串视为未修改；环境变量托管的 Key 被忽略并在 `env_managed` 中列出 |
| `/api/config/test/<app_id>` 🔒 | POST | 测试单个应用连通性（请求 Dify `/parameters`） |
| `/api/config/test-all` 🔒 | POST | 批量测试 6 个应用 |

`<app_id>` ∈ `A1 A2 A3 A4 R1 R2`（大小写不敏感）。

## 2. 项目 CRUD

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/projects` | GET | 列表。Query: `status`、`search`（匹配 name/department/activity_type）、`page`、`page_size`（1–200，非法值回落默认） |
| `/api/projects` | POST | 新建。Body: `{name, activity_type, department, date, target, budget, background}`，`name` 必填否则 400，状态默认 `draft` |
| `/api/projects/<id>` | GET | 详情，六个 `*_data` / `versions` / `feed` 字段会被解析为 JSON |
| `/api/projects/<id>` | PUT | 局部更新。仅接受列名白名单（`PROJECT_UPDATABLE`）内的字段，其余静默忽略；`*_data` / `versions` / `feed` 传对象自动序列化 |
| `/api/projects/<id>` 🔒 | DELETE | 删除（先写审计日志再删） |

### `projects` 关键字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `a1_data`..`r2_data` | JSON | 六个阶段的产物 |
| `versions` | JSON array | 版本历史（A4 草稿 + 人工确认的正式版） |
| `feed` | JSON array | 操作时间线 |
| `status` | text | `draft` / 其它自定义状态 |

## 3. Dify 代理

| 路由 | 方法 | 上游 | 说明 |
| --- | --- | --- | --- |
| `/api/dify/workflow/<app_id>` 🔒 | POST | `POST {base}/workflows/run` (blocking) | Body: `{inputs, user, project_id}` |
| `/api/dify/workflow-stream/<app_id>` 🔒 | POST | 同上 (streaming) | 返回 `text/event-stream` |
| `/api/dify/chat/<app_id>` 🔒 | POST | `POST {base}/chat-messages` (blocking) | Body: `{query, inputs, user, conversation_id, project_id}` |
| `/api/dify/chat-stream/<app_id>` 🔒 | POST | 同上 (streaming) | 返回 `text/event-stream` |

- 超时 `DIFY_TIMEOUT`（默认 300s），证书校验由 `DIFY_VERIFY_SSL` 控制（默认开）
- base_url 与 Key 经 `resolve_dify()` 合并：环境变量优先，其次 `config` 表（解密后）
- 每次调用写 `dify_calls` 表（流式用独立连接留痕）
- 未配置 base_url 或对应 Key 时返回 400；上游异常返回 502

## 4. 统计与日志

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/stats` | GET | 项目数/状态分布、Dify 调用数/应用分布/状态分布、平均耗时、近 7 天趋势 |
| `/api/logs` | GET | 操作审计日志。Query: `module`、`project_id`、`page`、`page_size` |
| `/api/dify-calls` | GET | Dify 调用记录。Query: `app_id`、`status`、`project_id`、`page`、`page_size` |

## 5. 数据导出 / 导入

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/export` 🔒 | GET | 全量导出：`config` + 所有 `projects`。Key **默认脱敏**；加 `?include_secrets=1` 才导出明文，响应含 `secrets_included` 标记 |
| `/api/import` 🔒 | POST | 全量导入：Body 同导出结构。掩码串会被跳过；Key 按加密策略入库；`projects` 逐条 INSERT |

## 6. 数据表

见 `database.py`：`config`（单行）、`projects`、`logs`、`dify_calls`，均带常用索引。
`logs` / `dify_calls` 对 `projects` 有外键 `ON DELETE SET NULL`。
`config` 表的 `key_*` 列在设置 `APP_SECRET_KEY` 时以 `enc:v1:` 前缀的 Fernet 密文存储。

---

## 安全与运维

| 维度 | 现状 |
| --- | --- |
| 鉴权 | 🔒 接口需 HTTP Basic（`ADMIN_TOKEN`）；未配置为显式开发模式（`X-Auth-Warning` + 启动告警） |
| API Key | 环境变量优先；DB 存储支持 Fernet 加密；GET / export 默认脱敏 |
| 传输 | Dify 调用默认校验 TLS 证书（`DIFY_VERIFY_SSL`） |
| 输入 | 请求体 `MAX_CONTENT_LENGTH` 限制；分页参数越界回落；PUT 列名白名单防注入；JSON 解析失败不抛 500 |
| 连接 | `teardown_appcontext` 统一关闭，异常路径不泄漏 |
| 错误 | `HTTPException` / 未捕获异常统一转 JSON，未捕获异常写 `logger.exception` |
| 健康检查 | `/healthz` |
| 测试 | `tests/` 下 `pytest`，覆盖配置往返 / 加密 / 项目 CRUD / 鉴权 / 脱敏 / 错误处理 |

### 待办

| 项 | 现状 | 计划 |
| --- | --- | --- |
| 数据库 | SQLite 单文件，Render 免费实例重启丢数据 | 持久盘或 Postgres |
| 分级鉴权 | 只有「管理员 / 开发模式全开」两档；`/api/projects` 读写无鉴权，`/api/dify/*` 复用管理员档 | 增加业务用户档（会话 / 项目级权限） |
| 可观测性 | 仅首尾留痕，无 trace id | 贯穿式 trace |
| 评测 | 人工执行 | 自动化 + CI |
