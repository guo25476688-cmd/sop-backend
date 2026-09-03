# 企业级 AI 应用运营平台 · 运行原型

> AI 驱动的企业级智能应用运营平台 ｜ AI Agent 产品架构设计
>
> 面向企业「AI 需求分散、场景价值难判断、知识资产难复用、应用效果缺乏统一评估」四类问题，
> 从 0→1 设计的企业级 AI 应用运营平台。本仓库是该平台的**可运行原型**，
> 以「活动运营 SOP」作为首个落地场景，验证「场景发现 → 需求分析 → 方案设计 → 应用建设 → 推广复用 → 效果评估」六大模块的端到端闭环。

技术关键词：Dify Workflow、Chatflow、RAG、LLM、LangChain、Python

**在线体验**：<https://sop-backend-yuoa.onrender.com>
（业务工作台 `/` ｜ 运营管理后台 `/admin`）

> Render 免费实例，闲置后会休眠，**首次打开需等 30–60 秒冷启动**，属正常现象。
> 演示环境开启了 `DEMO_MODE`：未接真实 Dify Key 的 AI 步骤会返回**预置示例内容**（以「高管 AI 应用实战工作坊」为样例），
> 因此可以从「新建项目」一路走到「复盘报告」看完整流程。这层降级的实现见 [main.py](main.py) 的 Dify 代理层与 [demo_fixtures.py](demo_fixtures.py)。

---

## 面试官 5 分钟导览

| 想看什么 | 去哪里 |
| --- | --- |
| 产品架构思路：六大模块、数据契约、人工卡点的取舍 | [docs/01-architecture.md](docs/01-architecture.md) |
| RAG 体系设计：按用途分四库、分层切片、关键词+向量双路召回 | [docs/02-rag-design.md](docs/02-rag-design.md) |
| 任务编排：能力模块化 + Dify Workflow/Chatflow 组合 | [docs/03-orchestration.md](docs/03-orchestration.md) |
| 质量评估：四维框架、50+ Case、BadCase 四类归因的定位口径 | [docs/04-evaluation.md](docs/04-evaluation.md) |
| 工程实现：鉴权、密钥加密、错误处理、测试 | [main.py](main.py) · [docs/05-api-reference.md](docs/05-api-reference.md) |

**在线走一遍**：打开在线体验 → 首页看六大模块闭环 → 点「新建项目」（已预填一个活动样例）→ 一路「确认」推进：SOP 大纲 → 执行主表 → 配套成果 → 复盘分析 → 复盘报告，注意每个高风险环节的人工确认卡点；`/admin` 看数据看板、Dify 调用记录、操作日志。

---

## 1. 这个仓库是什么

| | 说明 |
| --- | --- |
| **定位** | 平台产品原型 + 后端服务，用于演示端到端闭环，不是生产系统 |
| **前端** | 两个零依赖单文件页面：`static/index.html`（业务工作台）、`static/admin.html`（运营管理后台） |
| **后端** | Flask 单体应用 `main.py`，职责是 Dify 代理 + 项目/配置/日志持久化 |
| **AI 编排** | 全部在 Dify 上实现（6 个应用，见 [§4](#4-多节点任务编排)），后端只做鉴权转发与调用留痕 |
| **知识库** | 四类企业知识资产在 Dify 知识库中维护，设计口径见 [docs/02-rag-design.md](docs/02-rag-design.md) |
| **部署** | Render（`render.yaml` / `Procfile`），SQLite 本地文件存储 |

> **为什么用「活动运营」当样板场景**：它同时具备"需求零散、方案要复用历史经验、成果要结构化、效果要复盘"四个特征，
> 是验证平台六大模块最小而完整的切片。平台设计本身是场景无关的。

---

## 2. 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（默认 8000 端口）
python main.py
# 或
bash start.sh 8000

# 3. 打开页面
#   业务工作台   http://localhost:8000/
#   运营管理后台 http://localhost:8000/admin
```

首次启动会自动创建 SQLite 库 `sop_platform.db`。
在「管理后台 → API 配置」填入 Dify 平台地址与 6 个应用的 API Key 后即可跑通完整链路。

本地配置复制 `.env.example` 为 `.env`（已在 `.gitignore` 中）。完整变量清单见该文件，常用：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 监听端口 |
| `FLASK_DEBUG` | `0` | `1` 开启调试模式 |
| `SOP_DB_PATH` | `./sop_platform.db` | SQLite 文件路径 |
| `APP_SECRET_KEY` | 空 | Fernet 密钥；设置后数据库里的 API Key 加密存储 |
| `ADMIN_TOKEN` | 空 | 设置后 `/admin` 与写接口需 HTTP Basic（密码=该值）；不设为开放的开发模式 |
| `DIFY_BASE_URL` / `DIFY_KEY_A1..R2` | 空 | 提供则作为权威来源，覆盖后台 UI 配置 |
| `DIFY_VERIFY_SSL` | `1` | 自建 Dify 用自签名证书时设 `0` |
| `DEMO_MODE` | `0` | `1` 时未配置 Key 的应用返回 [demo_fixtures.py](demo_fixtures.py) 的预置内容 |

> **开发模式**（未设 `ADMIN_TOKEN`）下所有接口开放，响应头带 `X-Auth-Warning`，启动日志打印告警。公网部署务必设置 `ADMIN_TOKEN` 与 `APP_SECRET_KEY`。
>
> 设置 `ADMIN_TOKEN` 后：`/admin` 页面用浏览器 HTTP Basic 弹窗登录（用户名任意）；前台在「功能接入管理 → 管理令牌」填入同一个值，之后写接口与 Dify 调用会自动带 `X-Admin-Token` 头。

### 测试

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 3. 六大模块与生命周期架构

平台把「一个 AI 需求从被发现到产生可复用资产」拆成六个模块，各模块之间以结构化数据流转：

```
场景发现 ──> 需求分析 ──> 方案设计 ──[人工审核]──> 应用建设 ──> 推广复用 ──> 效果评估
   │            │            │                        │            │            │
 需求线索     结构化需求    应用方案 + 资源规划       结构化成果   复用记录      四维评测
                                                  [成果输出人工审核]              │
                                                                                 └─> 反馈回流知识库
```

**只在「方案设计」与「成果输出」两个高风险环节设人工卡点，其余环节全自动执行。**

在本原型的「活动运营」场景下，六大模块映射到 5 个可见阶段 + 1 个横切助手：

| 生命周期模块 | 场景内阶段 | 对应 Dify 应用 |
| --- | --- | --- |
| 场景发现 / 需求分析 | 01 · 策划：需求录入 + 历史经验检索 | A1 SOP 大纲生成 |
| 方案设计 ⛳（人工卡点） | 02 · 执行：大纲 → 执行主表 | A2 执行主表生成 |
| 应用建设 | 03 · 成果：配套结构化成果生成 | A3 配套成果生成 |
| （横切）方案调整 | AI 修改助手：对话式修改 + 影响预览 | A4 AI 修改助手（Chatflow） |
| 效果评估 | 04 · 复盘：数据口径校验 + 效益判断 | R1 活动复盘分析 |
| 效果评估 ⛳（人工卡点） | 05 · 沉淀：复盘报告 + 行动计划 | R2 复盘报告生成 |
| 推广复用 | 反馈回流：用户修改沉淀回知识库 | 见 [docs/04-evaluation.md](docs/04-evaluation.md#反馈回流) |

详见 [docs/01-architecture.md](docs/01-architecture.md)。

---

## 4. 多节点任务编排

六项通用能力被拆成可复用模块，在 Dify 上通过上下文传递与条件分支组合成完整链路：

| 编号 | 应用 | 类型 | 输入变量 | 能力模块 |
| --- | --- | --- | --- | --- |
| **A1** | SOP 大纲生成 | Workflow | `activity_name, activity_type, background, date, target, budget, department` | 需求理解 + 知识检索 + 方案生成 |
| **A2** | 执行主表生成 | Workflow | `sop_outline, project_info` | 方案生成 + 资源规划 |
| **A3** | 配套成果生成 | Workflow | `task_table, project_info, asset_type` | 成果输出 |
| **A4** | AI 修改助手 | Chatflow | `project_context`（对话输入） | 方案生成（增量） |
| **R1** | 活动复盘分析 | Workflow | `event_data, task_table, feedback_data` | 复盘分析 |
| **R2** | 复盘报告生成 | Workflow | `r1_analysis, project_info` | 成果输出 |

后端对这 6 个应用提供统一代理协议：`/api/dify/workflow/<app_id>`、`/api/dify/chat/<app_id>`（及对应 `-stream` 版本），
自动注入对应 API Key、记录输入/输出/耗时/状态到 `dify_calls` 表。详见 [docs/03-orchestration.md](docs/03-orchestration.md)。

---

## 5. 企业级 RAG 知识体系

按**知识用途**而非文档来源划分四类资产：

| 知识库 | 用途 | 召回场景 |
| --- | --- | --- |
| 案例库 | 相似历史活动的完整方案 | A1 大纲生成时提供结构参考 |
| 流程规范库 | 公司制度、审批流、物料标准 | A2/A3 生成时做合规约束 |
| 应用方案库 | 已沉淀的可复用 SOP 模板 | A1/A2 命中同类型直接复用 |
| 复盘优化库 | 历史复盘结论与改进项 | R1/R2 提供归因与行动参考 |

- **分层切片策略** + Metadata 字段设计（活动类型、部门、年份、知识层级…）
- **关键词 + 向量双路召回**：企业知识里产品型号、部门简称等专有名词密集，纯向量检索精确匹配召回率偏低，关键词通路兜底
- 当前语料：累计接入 **86 篇文档、约 15 万字**

详见 [docs/02-rag-design.md](docs/02-rag-design.md)。

---

## 6. 质量评估机制

四维评测框架 + 测试—定位—优化—回归闭环：

| 维度 | 检查点 |
| --- | --- |
| 召回准确性 | 该命中的知识是否召回、Top-K 是否相关 |
| 内容完整性 | 关键字段是否齐全、是否遗漏必备环节 |
| 结构化输出规范性 | 是否符合约定 Schema、可否被前端解析 |
| 异常识别能力 | 缺失信息是否标注"待确认"而非编造 |

- 设计 **50+ 条测试 Case**，人工 Grader + 规则校验，多轮回归
- BadCase 归因为四类：知识检索 / 上下文传递 / Prompt 约束 / Workflow 逻辑，各有可复现定位口径
- 对应修复手段：调整切片粒度 / 补充节点上下文 / 增加输出 Schema 约束 / 修正编排分支
- 反馈回流机制：用户在前端的修改沉淀回知识库

详见 [docs/04-evaluation.md](docs/04-evaluation.md)。

---

## 7. 产出

- Web 端产品原型：串联需求提交 → 方案生成 → 应用使用 → 效果反馈的完整流程
- 规划能力：项目管理、权限控制、版本管理、成果中心、API 接入
- 结构化内容自动生成：AI 应用方案、流程文档、执行清单、复盘报告

---

## 8. 目录结构

```
sop-backend/
├── main.py              # Flask 后端：前端托管 + API 配置 + 项目 CRUD + Dify 代理 + 统计日志
├── config.py            # 集中环境变量配置（12-Factor）
├── demo_fixtures.py     # DEMO_MODE 下代替真实 Dify 调用的预置内容
├── database.py          # SQLite 建表 + API Key 透明加密
├── requirements.txt / requirements-dev.txt
├── .env.example
├── render.yaml / Procfile / start.sh
├── static/
│   ├── index.html       # 业务工作台（单文件）
│   └── admin.html       # 运营管理后台（单文件）
├── tests/               # pytest（API 层）
└── docs/
    ├── 01-architecture.md      # 生命周期六模块与数据流转
    ├── 02-rag-design.md        # 四类知识库 / 切片 / 双路召回
    ├── 03-orchestration.md     # Dify 编排与后端代理协议
    ├── 04-evaluation.md        # 四维评测与 BadCase 闭环
    └── 05-api-reference.md     # 后端 HTTP API
```

## 9. 工程化现状 / Roadmap

已落地（见 [docs/05-api-reference.md](docs/05-api-reference.md#安全与运维)）：

- ✅ API Key 支持环境变量注入 + Fernet 加密列，API 响应与导出默认脱敏
- ✅ `/admin` 与写接口 HTTP Basic 鉴权（`ADMIN_TOKEN`），未配置时为显式开发模式
- ✅ 统一 JSON 错误处理、请求体大小限制、连接 teardown、列名白名单
- ✅ `pytest` 覆盖 API 层（配置往返 / 加密 / 项目 CRUD / 鉴权 / 脱敏）
- ✅ `/healthz` 健康检查

待办：

- Render 免费实例 SQLite 会随重启丢失 —— 挂载持久盘或切 Postgres
- 公网部署时业务前台（`/`、`/api/dify/*`）也需要面向业务用户的鉴权，当前仅保护管理面
- 贯穿式 trace id、评测自动化 + CI
