# 测试计划 AI 汇总 · 企业微信推送 设计文档

> 目标：新建/编辑测试计划时，可任选一个「当前用户创建的 Agent」；保存计划时自动为该 Agent 创建会话（不提供前端展示）。批量执行 / 定时执行完成后，把本轮已执行用例的**标题、预期结果、执行结果、结果描述**整合后发给该会话（**非流式**），拿到 AI 返回结果后再推送到企业微信群机器人。若 AI 返回报错，则回退为原来的统计结果推送。

---

## 1. 现状梳理

### 1.1 现有 Agent / 会话 / 对话链路（已确认可复用）
| 能力 | 位置 | 形态 |
|---|---|---|
| 当前用户 Agent 列表 | `GET /api/v1/agent/agents?scope=mine`（[agent.py L116](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/api/v1/agent.py#L116-L132)，依赖 `get_current_active_user` + `require_agent_enabled`） | JWT，仅自己的 Agent |
| 创建会话 | `AgentService.create_conversation(user_id, ConversationCreate(agent_id, title))`（[agent_service.py L474](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/agent_service.py#L474-L505)） | 校验 agent 属于 user 且启用、LLM 可用 |
| 非流式对话 | `AgentService.send_message(user_id, conv_id, content) -> {"reply": ...}`（[agent_service.py L580](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/agent_service.py#L580-L633)） | 写 user 消息→run_round→写 assistant 消息 |
| 会话模型 | `AgentConversation`（[agent_conversation.py](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/models/agent_conversation.py)）：`user_id/agent_id/thread_id/config_hash/config_snapshot/status` | 关键守卫：`config_hash` 变更后禁止续聊 |

**注意**：`send_message` 有配置快照守卫——会话创建后若 Agent 的 LLM/提示词/工具变更，再次发送会抛 `ConflictException("Agent 配置已变更，请新建会话继续")`。后台推送时需捕获并回退统计。

### 1.2 现有企业微信通知链路
- 消息组装 `_build_notify_message`（[wecom_service.py L106](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/wecom_service.py#L106-L158)）：统计 + 失败明细 + 报告链接，`markdown` 类型
- 发送 `send_markdown`（[wecom_service.py L71](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/wecom_service.py#L71-L89)），单条按 `MAX_MESSAGE_BYTES=4000` 字节截断
- 入口 `notify_plan_finished`（[wecom_service.py L280](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/wecom_service.py#L280-L387)）：
  - 批量执行：`plan_service.execute_auto_cases` 的 `done_callback`（[plan_service.py L509-543](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/plan_service.py#L509-L543)）
  - 定时执行：`schedule_service._run_schedule_batch`（[schedule_service.py L235-274](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/schedule_service.py#L235-L274)）
- 用例结果来源：`PlanTestCase.result / result_desc` + `TestCase.title / expected_result`（本轮 `entries_ptc_ids` 过滤）

### 1.3 企业微信群机器人限制（本次必须遵守）
- **text 类型**：单条消息 **≤ 2048 字节**
- **markdown 类型**：单条 ≤ 4096 字节
- **限频**：每分钟 **最多 20 条**
- AI 汇总正文为自由文本 → 用 **text** 类型发送，需**分片**（每条 ≤2048）并按限频发送

---

## 2. 数据模型变更

`plans` 表新增两列（迁移 `0005_plan_agent_push.py`）：

| 列 | 类型 | 说明 |
|---|---|---|
| `agent_id` | int, FK `agent_definitions.id`, NULL | 计划绑定的 Agent |
| `agent_conversation_id` | int, FK `agent_conversations.id`, NULL, **Unique** | 保存时创建/复用的会话，一个计划唯一绑定一个会话 |

- 复用现有 `robot_ids`（JSONB）作为推送目标机器人，不新增机器人字段。
- **不删除**已解绑/被替换的旧会话（保留历史对话），仅解绑 `agent_conversation_id` 引用。

---

## 3. 交互接口与校验

### 3.1 前端选择 Agent（下拉）
- 复用现有 `GET /api/v1/agent/agents?scope=mine`：仅返回当前用户的 Agent（`id`、`name`）。
- 仅在「测试计划新增/编辑」弹窗展示；单选。
- **依赖注意**：该接口带 `require_agent_enabled`，若全局 Agent 未启用会 403 → 前端隐藏 Agent 选择并给出「Agent 服务未启用」提示，计划仍可正常创建/保存（只是不绑定）。

### 3.2 计划保存（create / update）新增 `agent_id`
`PlanCreate` / `PlanUpdate` 增加可选 `agent_id: int | None`；`PlanResponse` 增加 `agent_id`、`agent_name`（便于回显）。`robot_ids` 逻辑不变。

### 3.3 保存计划的会话编排（后端 plan_service）
- **校验**：`agent_id` 必须属于「保存者」（用 `actor_user_id`）；Agent/其 LLM 必须启用（复用 `AgentService` 校验逻辑，不重复写）。
- **新建**（`agent_id` 非空）：调用 `AgentService.create_conversation(user_id, agent_id, title="测试计划<name>结果汇总")` → 存 `agent_id` + 返回的 `conversation_id`。
- **编辑**：
  - `agent_id` 变更 → 新建会话并替换引用（旧会话保留、解绑）。
  - `agent_id` 未变 → 沿用原会话，不重建。
  - `agent_id` 清空 → 置空引用（不删会话）。
- **actor 边界**：若要绑定 Agent，保存者必须是真实用户（`actor_user_id` 有效）。若请求来自无归属用户的 API Key，绑定 Agent 阶段直接提示需用真实登录用户操作（或忽略绑定，记录日志）。

---

## 4. 执行完成后通知流程改造（核心）

改造 `notify_plan_finished`（保留原有签名与旁路语义：任何失败不阻塞执行主流程、不重试）。

### 4.1 分支
```
plan.agent_conversation_id 存在？
  是 ─→ 组装用例文本 → 非流式 send_message → 成功？→ 是 → 把 AI reply 分片推送到机器人(text)
                                        │                      └ 否 → 回退统计 markdown 推送
  否 ─→ 依决策项 D1：是否仍直接推统计（见 §6）
```

### 4.2 组装 send_message 的 prompt（长度受限）
- 遍历本轮 `rows`（`entries_ptc_ids` 过滤，同现有实现）：逐条输出
  `[结果] 标题\n预期：{tc.expected_result}\n实际结果：{pt.result}\n结果描述：{pt.result_desc}`
- **长度守卫**：`MessageSend.content` 上限 10000（现有 schema 限制）。用例较多时**截断**：优先保失败/阻塞用例，整体超出则分段取前 N 条并附「其余 X 条省略」。
- 每字段做单行化（`\n→空格`）+ 长度截断（预期结果取前 ~200、结果描述取前 ~500），防止单条 prompt 过大。

### 4.3 调用 Agent 会话（非流式）
- 使用独立 `AsyncSession` + `AgentService.send_message(conv.user_id, conv_id, prompt)`。
- **不经过 HTTP 路由**，直接调用 service（无 `require_agent_enabled` 校验，后台任务也不应有）。
- 结果取 `reply` 字符串。
- **异常兜底**：捕获全部异常（AI 报错 / 超时 / config_hash 守卫命中 `ConflictException` / 会话归档），记录日志并走**回退统计**分支（绝不向上抛）。

### 4.4 分片推送（text 类型，遵守 2048 字节 & 20 条/分钟）
- 新增 `send_text(webhook_url, secret, content)`：`msgtype="text"`，单条 **≤2048 字节**（复用 `_truncate_bytes` 字节安全截断，但这里改为按 2048）。
- 新增 `send_content_multipart(...)`：
  - 把 AI reply 按 2048 字节边界切分为多条（按 `\n` 断行，避免拆词/拆中文字节，UTF-8 字节安全），**内容完整保留，不做丢弃**。
  - **限频**：企业微信对每个机器人限频为**每分钟 ≤ 20 条**（一天上限 24×60×20 条）。分片后逐条发送，通过条间 `sleep` 控制节奏，保证**同一机器人在任一自然分钟内不超过 20 条**；多个机器人各自独立限频。
  - 机器人维度逐条发送，失败仅记日志。
  - 多 worker / 多进程注意：进程级限频计数不可靠 → 采用**保守节奏**（如每条间隔几秒）结合每分钟上限双保险；不做跨进程分布式限频（可后续 Redis）。
- **回退统计**分支复用现有 `_build_notify_message` + `send_markdown`（markdown，≤4000 字节，限频另处理：统计消息单条，天然满足）。

### 4.5 触发点（保持不变，不改调用方签名）
- 批量 `done_callback`、定时 `_run_schedule_batch` 尾部分别调用 `notify_plan_finished(...)`，签名不变。

---

## 5. 前端改动

- `TestPlanManage.vue` / `TestPlanDetail.vue` 弹窗（新增/编辑）：
  - 新增「AI 结果汇总 Agent」单选下拉（数据源 `GET /agent/agents?scope=mine`，仅列启用且属于当前用户的 Agent；未启用 Agent 服务时隐藏）。
  - 保存 payload 增加 `agent_id`；编辑回显 `agent.agent_name`。
  - 已有 isLoading/loading 态复用。
- `frontend/src/api/plan.js`：`createPlan/updatePlan` 增加 `agent_id`。

---

## 6. 已确认决策项

- **D1｜未配 Agent、仅配机器人**的计划：执行完成后**仍直接推统计**（向后兼容，机器人推送不依赖 Agent）。凡配了 Agent 且 AI 报错，一律回退统计推送。
- **D2｜编辑计划更换 Agent**：旧会话**保留并解绑**（历史对话留档，不新增删除逻辑）。
- **D3｜AI reply 超长**：按换行断句分片，**总弃 ≤ AI 结**超出部丢弃，优先保留 AI 结论
- **D4｜限频**：采用「单机器人 次+ s 做+小间隔

---

## 7. 迁移 & 部署

1. `alembic upgrade head`（应用 0005：plans 加 `agent_id`、`agent_conversation_id`）
2. `python -m scripts.seed_data`（无新权限，幂等即可；不强制）
3. 后端重启（新增 service 改动）
4. 前端 `npm run build`

## 8. 验证用例

| # | 场景 | 预期 |
|---|---|---|
| V1 | 新建计划勾选 Agent → 保存 | 返回 `agent_id`/`agent_name`；DB plan 有 conversation_id |
| V2 | 编辑不改 Agent 再保存 | 不新建会话（conversation_id 不变） |
| V3 | 编辑改 Agent 再保存 | 链接新会话，旧会话保留解绑 |
| V4 | 批量/定时执行完成 | 群里收到 AI 汇总 text 消息 |
| V5 | LLM 报错（改坏 LLM/reply 抛错）| 收到原统计 markdown |
| V6 | 未配 Agent 且 D1=A | 收到统计 |
| V7 | AI reply 超 2048 字节 | 分片为多条，每条 ≤2048，按每分钟 ≤20 条限频发送，内容完整保留 |
| V8 | 只配机器人不配 Agent 且 D1=B | 不推送 |