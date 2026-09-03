"""
演示数据 —— DEMO_MODE 开启且对应应用未配置真实 Dify Key 时，
后端用这里的预置内容代替真实 Dify 调用，让完整链路可被走通。

内容以「高管 AI 应用实战工作坊」为样例场景。
"""

import json

_A1 = """# 高管 AI 应用实战工作坊 · SOP 大纲

> 依据「培训 / 工作坊」活动类型，检索案例库中 3 篇相似高管培训方案生成。历史数据仅供参考，需人工确认。

## 阶段一 · 需求对齐与画像（活动前 4 周）
- 与业务负责人访谈，明确本次工作坊要解决的真实业务问题
- 收集参训高管所在部门的 AI 应用现状，形成能力画像
- 产出：培训目标说明书、学员画像表

## 阶段二 · 课程与案例设计（活动前 3 周）
- 按「认知 — 实操 — 落地」三段式设计课程结构
- 每个业务线准备 1 个真实场景作为课堂练习素材
- 产出：课程大纲、案例包、讲师手册

## 阶段三 · 会务与物料筹备（活动前 2 周）
- 场地、设备、网络与 AI 工具账号开通
- 学员分组（跨部门混编，每组 6 人）
- 产出：会务清单、分组名单、物料交付确认单

## 阶段四 · 现场执行（活动当天）
- 上午：认知重塑 + 工具实操
- 下午：分组实战 + 成果路演
- 产出：各组行动计划、现场记录

## 阶段五 · 训后跟踪与复盘（活动后 2 周）
- 第 1 周：各组提交落地进展
- 第 2 周：收集反馈数据，输出复盘报告
- 产出：训后跟踪表、复盘报告

**待确认项**：参训人数（预估 102 人）、预算上限（预估 2 万元）、讲师人选。
"""

_A2 = json.dumps([
    {"wbs": "1.1", "stage": "需求对齐", "name": "业务负责人访谈",
     "action": "1v1 访谈 6 条业务线负责人，明确培训要解决的问题",
     "deliverable": "培训目标说明书", "owner": "培训部 · 李明", "collaborator": "各业务线",
     "deadline": "活动前 4 周", "budget": "—", "dependency": "—",
     "acceptance": "6 条业务线目标全部书面确认", "status": "待启动", "remark": ""},
    {"wbs": "1.2", "stage": "需求对齐", "name": "学员 AI 能力画像",
     "action": "问卷 + 部门数据，形成参训高管能力画像表",
     "deliverable": "学员画像表", "owner": "培训部 · 王芳", "collaborator": "HRBP",
     "deadline": "活动前 3 周", "budget": "—", "dependency": "1.1",
     "acceptance": "回收率 ≥ 90%", "status": "待启动", "remark": ""},
    {"wbs": "2.1", "stage": "课程设计", "name": "三段式课程大纲",
     "action": "按认知—实操—落地设计半天课程结构",
     "deliverable": "课程大纲 v1", "owner": "外部讲师 · 张老师", "collaborator": "培训部",
     "deadline": "活动前 2 周", "budget": "12,000 元", "dependency": "1.1,1.2",
     "acceptance": "内部评审通过", "status": "待启动", "remark": "讲师费用占预算主要部分"},
    {"wbs": "2.2", "stage": "课程设计", "name": "真实案例包",
     "action": "每业务线产出 1 个课堂练习场景 + 脱敏数据",
     "deliverable": "案例包（6 个）", "owner": "各业务线", "collaborator": "培训部",
     "deadline": "活动前 2 周", "budget": "—", "dependency": "2.1",
     "acceptance": "6 个案例齐备且脱敏合规", "status": "待启动", "remark": ""},
    {"wbs": "3.1", "stage": "会务筹备", "name": "场地与工具账号",
     "action": "预订场地，开通 AI 工具试用账号 102 个",
     "deliverable": "会务清单", "owner": "行政部 · 陈刚", "collaborator": "IT",
     "deadline": "活动前 1 周", "budget": "5,000 元", "dependency": "—",
     "acceptance": "账号可登录率 100%", "status": "待启动", "remark": ""},
    {"wbs": "3.2", "stage": "会务筹备", "name": "跨部门分组",
     "action": "17 组，每组 6 人，跨部门混编",
     "deliverable": "分组名单", "owner": "培训部 · 王芳", "collaborator": "HRBP",
     "deadline": "活动前 3 天", "budget": "—", "dependency": "1.2",
     "acceptance": "无同部门扎堆", "status": "待启动", "remark": ""},
    {"wbs": "4.1", "stage": "现场执行", "name": "分组实战与路演",
     "action": "下午分组产出行动计划并路演，讲师点评",
     "deliverable": "17 份行动计划", "owner": "外部讲师 + 培训部", "collaborator": "全体学员",
     "deadline": "活动当天", "budget": "—", "dependency": "2.2,3.1,3.2",
     "acceptance": "每组交付 1 份可落地计划", "status": "待启动", "remark": ""},
    {"wbs": "5.1", "stage": "训后跟踪", "name": "落地进展跟踪",
     "action": "训后第 1、2 周各收集一次进展",
     "deliverable": "训后跟踪表", "owner": "培训部 · 李明", "collaborator": "各组组长",
     "deadline": "活动后 2 周", "budget": "—", "dependency": "4.1",
     "acceptance": "≥ 70% 小组有实质进展", "status": "待启动", "remark": "口径可调整为 3 周"},
], ensure_ascii=False)

_A3 = """# 配套成果包（示例生成）

## 一、预算明细表
| 科目 | 金额 | 说明 |
| --- | --- | --- |
| 讲师费 | 12,000 | 半天工作坊 + 案例设计 |
| 场地与设备 | 3,500 | 内部会议中心 |
| AI 工具账号 | 1,500 | 102 个 × 试用 |
| 物料与茶歇 | 2,000 | 手册、桌牌、茶歇 |
| 机动 | 1,000 | — |
| **合计** | **20,000** | 与预算上限持平 |

## 二、人员分工表
- 项目负责人：培训部 · 李明（总协调、训后跟踪）
- 课程对接：培训部 · 王芳（讲师、学员、分组）
- 会务保障：行政部 · 陈刚（场地、设备、物料）
- 技术支持：IT（工具账号、现场网络）

## 三、物料清单
学员手册 ×102、桌牌 ×102、分组任务卡 ×17、路演评分表 ×17、签到表、反馈问卷（电子）

## 四、内部通知（草稿）
> 各位管理者：公司将于 8 月 26 日举办「高管 AI 应用实战工作坊」，
> 采用认知—实操—落地三段式，下午分组产出可落地的 AI 应用行动计划。
> 请提前开通工具账号并准备本部门一个真实业务场景。
"""

_R1 = """# 活动复盘分析（示例生成）

> 先核对数据来源与口径，再给效益判断。标注【事实】【推断】【待确认】。

## 一、数据口径核对
- 参训人数：98 / 102（**事实**，签到表）
- 满意度：4.6 / 5（**事实**，回收 89 份）
- 训后 2 周落地率：11 / 17 组启动（**事实**）；产生业务价值 3 组（**推断**，自评口径未统一）

## 二、效益判断
- 认知层面达成度高：87% 学员表示"改变了对 AI 的看法"（**事实**）
- 落地层面偏弱：多数小组卡在"没有数据"和"缺工具权限"（**推断**）
- ROI 暂**无法计算**：缺少落地项目的量化收益数据（**待确认**）

## 三、主要问题
1. 案例脱敏耗时超预期，2 个业务线案例活动前一天才到位
2. 下午实战时间不足，路演仓促
3. 训后跟踪缺乏强制节点，靠组长自觉

## 四、改进建议
- 案例包提前 3 周锁定，设为硬卡点
- 实战环节 +45 分钟，压缩上午理论
- 训后跟踪改为"第 1 周必交进展"，纳入部门考核
"""

_R2 = """# 高管 AI 应用实战工作坊 · 复盘报告

## 一、活动概述
2026-08-26 举办，实到 98 人，跨部门 17 组，采用认知—实操—落地三段式。

## 二、目标达成
| 目标 | 结果 | 判断 |
| --- | --- | --- |
| 提升高管 AI 认知 | 满意度 4.6，87% 表示认知改变 | 达成 |
| 产出可落地行动计划 | 17 份计划，11 组训后启动 | 部分达成 |
| 形成可复用培训模式 | 三段式结构 + 案例包机制沉淀 | 达成 |

## 三、经验沉淀（回流知识库）
- **可复用模板**：三段式课程结构、跨部门分组规则 → 应用方案库
- **踩坑记录**：案例脱敏需提前 3 周 → 复盘优化库
- **口径**：训后价值评估需统一自评标准 → 复盘优化库

## 四、下一步行动
1. 培训部：2 周内把三段式模板归档为标准 SOP
2. 各组组长：训后第 1 周提交进展（部门考核项）
3. 培训部 + IT：为落地项目开通正式工具权限

> 本报告基于人工确认后的 R1 结论生成。
"""

_CHAT = """已分析你的修改要求，涉及以下成果：

**受影响项**
- 执行主表 5.1「落地进展跟踪」：截止时间 `活动后 2 周` → `活动后 3 周`
- 复盘报告「下一步行动」第 2 条对应表述

**建议改法**
1. 5.1 任务 `deadline` 改为「活动后 3 周」，验收口径同步为「≥ 60% 小组有实质进展」
2. 训后跟踪节点由 2 次改为 3 次（第 1、2、3 周）

修改只会生成新草稿，不会覆盖当前正式版。确认后我再写入。
"""

WORKFLOW = {"A1": _A1, "A2": _A2, "A3": _A3, "R1": _R1, "R2": _R2}


def workflow_result(app_id: str) -> dict:
    """构造 Dify workflow blocking 响应的等价结构（兼容前端两种取值路径）。"""
    text = WORKFLOW.get(app_id.upper(), "（演示内容缺失）")
    outputs = {"text": text}
    return {
        "demo": True,
        "workflow_run_id": f"demo-{app_id.lower()}",
        "data": {"outputs": outputs, "status": "succeeded", "elapsed_time": 1.2},
        "outputs": outputs,
    }


def workflow_sse(app_id: str):
    """产出一串 SSE data 行（不含 'data:' 前缀），最后一条为 workflow_finished。"""
    text = WORKFLOW.get(app_id.upper(), "（演示内容缺失）")
    yield json.dumps({"event": "workflow_started", "data": {"id": f"demo-{app_id}"}}, ensure_ascii=False)
    for title in ("需求理解", "知识检索", "方案生成"):
        yield json.dumps({"event": "node_started", "data": {"title": title}}, ensure_ascii=False)
        yield json.dumps({"event": "node_finished", "data": {"title": title, "status": "succeeded"}}, ensure_ascii=False)
    yield json.dumps({"event": "workflow_finished",
                      "data": {"outputs": {"text": text}, "status": "succeeded"}}, ensure_ascii=False)


def chat_result() -> dict:
    return {"demo": True, "answer": _CHAT, "conversation_id": "demo-a4"}


def chat_sse():
    """把演示回答按段落切成若干 message 事件。"""
    for para in _CHAT.strip().split("\n\n"):
        yield json.dumps({"event": "message", "answer": para + "\n\n", "conversation_id": "demo-a4"}, ensure_ascii=False)
    yield json.dumps({"event": "message_end", "conversation_id": "demo-a4"}, ensure_ascii=False)
