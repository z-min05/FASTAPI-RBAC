# Agent（AI 助手）模块设计文档

> 目标：把 `D:\zzm\PythonTest\ZAI\langchain_test`（LangChain 1.x Agent Base 框架）**完全集成**到当前 FastAPI RBAC 系统，作为与"项目/用例管理"同级的**内置子模块**（AI 助手），复用现有分层、RBAC、前端体系。交互由本项目前端（Web 聊天页）完成，取代源项目 CLI。

## 1. 背景与目标

### 1.1 现状

- **langchain_test（源项目）**：LangChain 1.x Agent 基础框架，在 CLI（REPL）中运行验证，具备：
  - 统一 Agent 构建（`AgentBuilder` 封装 `create_agent`）
  - 多 LLM 供应商工厂（OpenAI / Azure / Anthropic / Ollama，`LLMFactory`）
  - 工具注册中心（`ToolRegistry` 自动发现）
  - 内置工具：`calculator`、`search`、`run_cmd`/`run_cmd_with_cd`、`mqtt_*`、`http_get`/`http_post`
  - 写操作 `pending_op` 二次确认流（面向 CLI）
  - 会话记忆（LangGraph Checkpointer：内存 / Postgres）、中间件（日志/Token/消息清洗）、Token 账本、系统提示词模板
- **当前系统（FastAPI-RBAC）**：FastAPI + SQLAlchemy(async) + PostgreSQL + Redis + Casbin RBAC（api/menu/button 三级域）；分层规范 `api → services → repositories → models`；统一响应 `{code,message,data}`、统一异常/分页、`require_permissions`、`get_db` 自动提交；前端 Vue3 + Ant Design Vue。已内置"测试管理（项目/用例）"等子模块。

### 1.2 目标（含调整）

1. Agent 作为**子模块完全集成**：数据表、Schema、Service、API、迁移、权限种子、前端页面均按现有模块规范新增，运行时相关代码收敛为领域子包。
2. **交互形态 = 本项目前端 Web 聊天页**；源项目 CLI 主循环、确认式交互均不引入。
3. **只保留安全的通用工具**：`calculator`、`search`（只读、无外部副作用），**移除**命令执行（run_cmd）、MQTT/HTTP-IoT（mqtt_*、http_*）类工具 → 因此无需 pending_op 二次确认机制。
4. 复用 RBAC：agent:* 菜单/按钮/接口权限；用户数据与登录态复用。
5. 会话/消息/Token 落库，可追溯；多用户/多会话隔离。
6. 一期**同步 HTTP 响应**，为 SSE 流式预留扩展位。

## 2. 源项目能力盘点与取舍

| 源模块 | 功能 | 集成方式 | 取舍说明 |
|---|---|---|---|
| `core/agent.py` AgentBuilder | 构建 Agent | 迁入 `app/agent/core/agent_builder.py` | 原样保留 |
| `core/llm_factory.py` LLMFactory | 多供应商创建 | 迁入 `app/agent/core/llm_factory.py` | 原样保留 |
| `tools/registry.py` ToolRegistry | 工具注册/发现 | 迁入 `app/agent/tools/registry.py` | 原样保留 |
| `tools/builtin/calculator_tool.py` | 安全计算 | 迁入 | 默认启用 |
| `tools/builtin/search_tool.py` | 搜索（模拟实现） | 迁入 | 默认启用（后续可接真实搜索 API） |
| `tools/builtin/cmd_tool.py` | Windows 命令执行 | **不迁移** | 风险过高，按需求移除 |
| `tools/builtin/iot_*.py` + `iot_clients.py` | MQTT 控制/配置/指令 + HTTP 数据平台 | **不迁移** | 依赖内网环境且属写操作，按需求移除 |
| `middleware/agent_middleware.py` | 日志+Token+消息清洗 | 迁入改造 | 去 rich 控制台，改 logger + 落库 |
| `memory/checkpointer.py` | InMemorySaver / PostgresSaver | 迁入 | 一期 memory + DB 消息表；生产可切 postgres |
| `prompts/templates.py` | 系统提示词 | 迁入 | 新增平台通用提示词模板 |
| `token/*` | Token 账本/统计 | 迁入为进程内缓冲 | 落库 `agent_token_records` |
| `app.py`（REPL 主循环） | CLI 交互/确认流 | **不迁移** | 交互由本项目前端 Chat 页承担；服务层只做同步 invoke |

> 说明：移除 run_cmd / mqtt / http 后，工具均为**只读、无副作用**的通用工具，不存在需要用户二次确认的写操作，因此源项目的 PENDING_OP 确认机制一并移除。

## 3. 总体架构

### 3.1 集成后目录（后端，子模块结构）

```
backend/app/
├── agent/                        # ★ Agent 运行时子包（领域层；langchain 依赖只在此包内引用）
│   ├── __init__.py
│   ├── config.py                 # 运行时配置组装（读 app.config.settings 的 AGENT_*）
│   ├── runtime.py                # Agent 进程级单例（懒加载 + 锁）；async invoke 封装
│   ├── core/
│   │   ├── agent_builder.py      # ← 迁自 core/agent.py
│   │   └── llm_factory.py        # ← 迁自 core/llm_factory.py
│   ├── tools/
│   │   ├── registry.py           # ← 迁自 tools/registry.py（注册 calculator/search）
│   │   └── builtin/
│   │       ├── calculator_tool.py  # ← 迁移
│   │       └── search_tool.py      # ← 迁移
│   ├── memory/checkpointer.py    # ← 迁移
│   ├── middleware/agent_middleware.py  # ← 迁移改造（logger 代替 rich）
│   ├── prompts/templates.py      # ← 迁移，补充平台通用提示词
│   └── token/                    # ledger / models / reporter（迁移，落库改造）
├── models/agent_conversation.py  # 会话表
├── models/agent_message.py       # 消息表
├── models/agent_token_record.py  # Token 记录表
├── schemas/agent.py              # 会话/消息/发送/统计请求响应
├── services/agent_service.py     # 会话 CRUD + 发送消息(invoke) + 历史 + 统计
└── api/v1/agent.py               # REST 路由（注册进 v1）
```

> 数据模型 / Schema / Service / 路由完全遵循现有模块（projects/testcases）分层与风格；`app/agent/` 仅承载 langchain 相关运行时，与业务分层解耦。

### 3.2 请求主链路

```
前端 Chat.vue
   │ POST /agent/conversations/{id}/messages {content}
   ▼
api/v1/agent.py  ── require_permissions("agent:chat")
   ▼
agent_service.send_message(conversation_id, content)
   ├─ 1. 校验会话归属（conversation.user_id == 当前用户）
   ├─ 2. 持久化 user 消息 → agent_messages
   ├─ 3. asyncio.wait_for(asyncio.to_thread(agent.invoke, input, config), timeout)
   │      └─ Agent(单例, thread_id 隔离) 内部：LLM ⇄ tools(calculator/search)
   │      └─ middleware 采集 token → TokenLedger(内存)
   ├─ 4. 持久化 assistant 消息（clean 文本 + token 数）
   ├─ 5. token 落库 agent_token_records
   └─ 返回 { reply, token:{...}, conversation_id }
```

### 3.3 Agent 单例与多进程

- `app/agent/runtime.py`：进程级懒加载单例（`threading.Lock` 双检锁，模式同 casbin_service）。
- 每次 invoke 携带 `{"configurable": {"thread_id": <conversation.thread_id>}}`，保证会话/用户状态隔离。
- 多 Worker：图实例每进程一份；Checkpointer 生产切 Postgres 后可跨 Worker 共享会话状态（见 4.5）。配置变更重启生效（v1 不做策略热更新）。

## 4. 核心组件设计

### 4.1 配置（Settings 扩展）

`app/config.py` 的 `Settings` 新增（`backend/.env` 注入）：

| 配置项 | 默认 | 说明 |
|---|---|---|
| `AGENT_ENABLED` | `false` | 总开关（关闭时 Agent 路由返回 503） |
| `AGENT_LLM_PROVIDER` | `openai` | 供应商（openai/azure/anthropic/ollama） |
| `AGENT_LLM_MODEL` | `gpt-4o-mini` | 模型名（默认轻量模型控制成本） |
| `AGENT_LLM_BASE_URL` | `""` | 兼容 OpenAI 服务地址（空=官方） |
| `AGENT_LLM_API_KEY` | `""` | 密钥（仅 .env，不入库不打印） |
| `AGENT_LLM_TEMPERATURE` | `0.3` | 采样温度 |
| `AGENT_LLM_MAX_TOKENS` | `2048` | 单次输出上限 |
| `AGENT_LLM_TIMEOUT` | `60` | 模型请求超时（秒） |
| `AGENT_INVOKE_TIMEOUT` | `180` | 单轮 Agent 总超时（秒） |
| `AGENT_SYSTEM_PROMPT` | `default` | 默认系统提示词模板名 |
| `AGENT_TOOLS_ENABLED` | `calculator,search` | 启用工具白名单（逗号分隔） |
| `AGENT_MEMORY_BACKEND` | `memory` | `memory` / `postgres`（checkpointer） |
| `AGENT_CHECKPOINT_DB_URI` | `""` | postgres 时必填（独立 sync 连接串） |

### 4.2 Agent 构建

迁移 `AgentBuilder` + `LLMFactory`，`runtime.py` 组装一次：

```
AgentBuilder()
  .with_llm(LLMFactory.create(...))
  .with_tools(白名单工具列表)          # registry 按 AGENT_TOOLS_ENABLED 过滤
  .with_system_prompt(get_system_prompt(key))   # 支持按会话 preset 覆盖
  .with_middleware(create_agent_middleware(ledger))
  .with_checkpointer(...)             # 见 4.5
  .build()
```

- **循环上限**：提示词约束 + 配置 `max_iterations=10`，避免工具空转烧 token。
- **超时保护**：路由/服务侧 `asyncio.wait_for(asyncio.to_thread(...), timeout=AGENT_INVOKE_TIMEOUT)`，超时返回友好错误。

### 4.3 工具集（移除 cmd / mqtt / http 后）

| 工具 | 类型 | 行为 | 说明 |
|---|---|---|---|
| `calculator` | 安全（只读） | 数值表达式求值（安全环境执行） | 默认启用 |
| `search` | 安全（只读） | 关键词搜索（源项目为模拟实现） | 默认启用，后续可接真实搜索 API |

设计要点：
- 工具全部**无外部副作用**，无二次确认需求；`registry` 保留工具发现/注册机制，便于后续扩展新工具。
- 若未来新增写/危险工具，须先走权限评审并增加确认机制（本期不做）。
- 工具异常信息脱敏后返回 LLM（不回显密钥/服务器路径细节）；logger 统一记录。

### 4.4 异步执行策略

- `agent.invoke` 为同步阻塞，**禁止直接在 async 路由调用**。
- 统一封装：`await asyncio.wait_for(asyncio.to_thread(agent.invoke, input, config), timeout)`，跑在线程池。
- 同会话并发发送加锁：同一 `conversation_id` 正在 invoke 时再次发送返回 409。

### 4.5 会话记忆

- 短期记忆：LangGraph Checkpointer。
  - 一期 `memory`（InMemorySaver）——结合 `agent_messages` 表提供跨重启可展示的历史与多轮上下文（多轮依赖 LangGraph state）。
  - 生产切 `postgres`（`langgraph-checkpoint-postgres`，独立连接串），会话状态跨 Worker/重启保留。
- 历史展示读 `agent_messages`（面向用户的消息，tool 内部往返不入表）。
- `thread_id` 全局唯一（`conv-{uuid}`），与 `agent_conversations.id` 一一映射。

### 4.6 Token 统计

- 中间件（迁自源项目，去 rich）每次模型调用写入进程内 `TokenLedger`；service 在 invoke 后 flush 到 `agent_token_records`（带 user_id/conversation_id/model/step）。
- 提供按会话 / 按用户汇总接口。

## 5. 数据模型

均继承 `BaseModel`（id/created_at/updated_at），`models/__init__.py` 注册。

**表 `agent_conversations`（会话）**

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | Integer | NOT NULL, FK→users.id, index | 所属用户 |
| title | String(200) | NOT NULL | 标题（首条消息截断或用户自定义） |
| thread_id | String(64) | NOT NULL, unique | LangGraph 线程 ID |
| agent_key | String(50) | NOT NULL, default 'default' | 提示词/工具 preset |
| model | String(100) | NULL | 模型快照 |
| status | String(20) | NOT NULL, default 'active' | active / archived |

**表 `agent_messages`（消息）**

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| conversation_id | Integer | NOT NULL, FK→agent_conversations.id(ondelete CASCADE), index | 会话 |
| role | String(20) | NOT NULL | user / assistant |
| content | Text | NULL | 文本内容 |
| token_total | Integer | NULL | 本条 assistant 消息生成 token（冗余展示） |

**表 `agent_token_records`（Token 记录）**

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | Integer | NOT NULL, FK→users.id, index | 使用者 |
| conversation_id | Integer | FK→agent_conversations.id | 归属会话 |
| model | String(100) | NOT NULL | 模型名 |
| step | Integer | NOT NULL | 会话内模型调用序号 |
| input_tokens / output_tokens | Integer | NOT NULL | 输入/输出 |
| total_tokens | Integer | NOT NULL | 合计 |

**迁移**：新增 `alembic/versions/0004_add_agent_tables.py`（down_revision=`0003_drop_testcase_run_order`）。

## 6. API 设计

统一前缀 `/api/v1/agent`，鉴权 `Bearer Token` + `require_permissions("agent:*")`；响应统一 `{code,message,data}`；分页复用 `PaginationParams`。

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/agent/conversations` | agent:chat | 创建会话（body: title/agent_key 可选）→ `{id, thread_id}` |
| GET | `/agent/conversations` | agent:chat | 我的会话列表（分页） |
| GET | `/agent/conversations/{id}/messages` | agent:chat | 会话历史消息（分页） |
| POST | `/agent/conversations/{id}/messages` | agent:chat | **发送消息** `{content}` → `{reply, token}`；invoke 超时/失败给友好错误 |
| DELETE | `/agent/conversations/{id}` | agent:delete | 删除会话（级联消息；Token 记录保留审计） |
| GET | `/agent/tools` | agent:chat | 当前可用工具列表（前端能力展示） |
| GET | `/agent/presets` | agent:chat | 可选 preset（提示词/模型组合） |
| GET | `/agent/stats/tokens` | agent:stats | 我的 Token 统计（汇总 + 分页明细） |

要点：
- 所有 `{id}` 操作校验 `conversation.user_id == current_user.id`（越权 403）。
- `AGENT_ENABLED=false` 时 agent 路由返回 503（前端提示功能未启用）。
- 发送消息为同步等待（最长约 3 分钟），前端 loading + 防重复提交（同会话并发 409）。

## 7. 权限、菜单与前端

### 7.1 权限与种子（scripts/seed_data.py 增量，幂等）

- 权限码：`agent:chat`、`agent:delete`、`agent:stats`（本期 3 个）。
- 菜单目录"AI 助手"（icon `RobotOutlined`，sort 按现有目录排），子菜单：
  - "Agent 对话" path `/agent/chat`，component `agent/Chat`，permission=`agent:chat`
  - 按钮：发送(agent:chat)、删除会话(agent:delete)、查看统计(agent:stats)
- 角色授权：admin 全授；user 授 `agent:chat`。
- 权限落库后经 `_sync_casbin` / `invalidate_policy` 联动（沿用测试管理模块种子模式）。

### 7.2 前端（用户交互层）

- `frontend/src/api/agent.js`：上表 API 封装。
- `frontend/src/pages/agent/Chat.vue`（路由 `/agent/chat` 静态注册，meta.title=Agent 对话）：
  - 左侧：我的会话列表（新建 / 切换 / 删除）
  - 右侧：消息流（user 右侧气泡；assistant 左侧 Markdown 渲染）
  - 输入区：发送框、发送中 loading + 禁用、Enter 发送
  - 底部/侧栏：本次与累计 Token 消耗
  - 会话标题取首条消息前 20 字（前端可编辑，v2）
- 无确认类交互（工具均为只读）。
- Markdown 渲染引入轻量依赖（如 `marked`）。

## 8. 实施任务拆解

| 阶段 | 任务 | 涉及文件（目标） |
|---|---|---|
| 1. 依赖与配置 | 新增 langchain/langgraph 等依赖；Settings 扩展 AGENT_* | `backend/requirements.txt`、`app/config.py`、`.env` |
| 2. 运行时层迁移 | 迁入 core / tools(calculator,search) / memory / middleware / prompts / token；rich→logger 改造 | `app/agent/**` |
| 3. runtime 单例 | 懒加载 Agent + checkpointer + invoke 线程池/超时封装 | `app/agent/runtime.py` |
| 4. 数据层 | 3 张表 Model + 0004 迁移 + Schema | `app/models/agent_*.py`、`alembic/versions/0004_*.py`、`app/schemas/agent.py` |
| 5. 服务层 | agent_service：会话 CRUD、send_message、历史、统计 | `app/services/agent_service.py` |
| 6. 路由 | `/agent` 路由 + v1 注册 | `app/api/v1/agent.py`、`app/api/v1/__init__.py` |
| 7. 权限与种子 | agent:* 权限、菜单/按钮、角色授权 | `scripts/seed_data.py` |
| 8. 前端 | api + Chat.vue + 路由 + 菜单图标 | `frontend/src/api/agent.js`、`pages/agent/Chat.vue`、`router/index.js`、`layouts/MainLayout.vue`(iconMap) |
| 9. 测试 | 黑盒：未登录 401；创建/列表/历史；发送消息（mock LLM 应答）；越权 403；删除；统计 | `backend/tests/test_agent.py` |

## 9. 风险与注意事项

1. **版本兼容**：源项目 `python>=3.10,<3.13` 与当前 3.11.15 满足；langchain>=1.2 / langgraph>=0.4 与现有 pydantic 2.10 的兼容性，实施第一步先 `pip install` 冒烟验证（最小可用 Demo 先行）。
2. **阻塞调用**：invoke 必须在线程池执行，勿阻塞事件循环。
3. **密钥安全**：`AGENT_LLM_API_KEY` 只进 `.env`，不进库不打印（日志脱敏）。
4. **多 Worker / 重启**：memory checkpointer 重启丢会话状态，历史仍可在 `agent_messages` 展示；生产推荐 postgres checkpointer。
5. **Token 成本**：默认轻量模型 + `max_tokens=2048` + `max_iterations=10`；未启用模块时通过 `AGENT_ENABLED` 直接关闭，避免无谓依赖加载。
6. **模拟搜索**：`search` 为源项目模拟实现，上线前应替换为真实搜索/知识检索，避免误导用户（列入后续演进）。
7. **新增工具纪律**：本期工具均为只读；未来新增写/危险工具必须先评审并设计确认机制。
8. **语言与定位**：默认提示词中立通用，可面向平台用户扩展（如测试用例知识问答，见第 10 节）。

## 10. 后续演进（本期不做）

- SSE / WebSocket 流式输出（`astream`）与发送中断
- 把测试用例库（testcases 表）作为工具让 Agent 检索、辅助编写用例
- 会话标题自动生成、会话改名/归档
- 真实搜索接入 / RAG 知识库（设备调试、测试规范等文档）
