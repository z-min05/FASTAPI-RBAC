# Agent 模块改造方案 V2（LLM/Agent 平台化管理）

> 在 V1（Agent 模块已落地：对话+消息+Token 统计）基础上重构：把"固定 .env 全局 LLM + preset 提示词映射"升级为**平台化配置**——LLM 由管理员在平台创建并入库，Agent 由用户自定义（选 LLM、自填提示词、自选工具），会话记忆改为 PostgreSQL 持久化。
>
> 本文档为**修改方案**，经确认后进入实施（实施期间将同步更新 V1 相关代码与文档）。

---

## 1. 变更动机与目标

| # | V1 现状 | 问题 | V2 目标 |
|---|---|---|---|
| 1 | LLM 固定写在 `.env`（`AGENT_LLM_*`），代码内单例 | 换模型/加供应商要改配置重启；Key 暴露在 env | LLM 配置入库，**仅超管**在页面创建/编辑/启停，普通用户只能查看与选择 |
| 2 | Agent 提示词走 `AGENT_SYSTEM_PROMPT=default/coder` 模板映射 | preset 与"用户自建 Agent"冲突 | 用户创建 Agent 时**直接输入文字提示词**，不落任何模板映射 |
| 3 | 全局单 Agent 实例，工具由 `AGENT_TOOLS_ENABLED` 固定 | 无法按 Agent 定制能力 | 创建 Agent 时**默认不勾选工具**，由用户按需勾选（calculator/search，注册表可扩展） |
| 4 | 会话只有 `agent_key/model` 两个弱字段，无 Agent 概念 | 无法表达"我建了多个 Agent 并选用" | 会话关联 `agent_id`，新建会话时选择自己的 Agent |
| 5 | 记忆 `AGENT_MEMORY_BACKEND=memory`（InMemorySaver） | 重启丢上下文 | 固定 **PostgreSQL Checkpointer**（langgraph-checkpoint-postgres），线程级串行安全 |
| 6 | 修改提示词/工具后无版本概念 | 旧会话图结构可能不兼容 | 会话保存**配置快照+hash**，Agent 变更后旧会话只读历史、禁止续聊（提示新建会话） |

---

## 2. 已确认的产品决策

1. **LLM**：只有超管能创建/编辑/删除（`agent:llm:manage`）；所有登录用户可查看列表并选用；API Key 一律掩码回显（`sk-****`）。
2. **Agent**：用户只能看/改自己的；超管可查看与操作全部（管理视图带归属人）。
3. **配置变更策略**：会话创建时快照 Agent 配置并计算 hash；发送前若 hash 不一致 → `409 配置已变更，请新建会话继续`；旧会话历史仍可查看。
4. **`.env` LLM 完全下架**：不预置"系统默认 LLM"，无 LLM 时超管先建（新建 Agent 下拉需至少 1 条 enabled LLM）。
5. 记忆后端固定 `postgres`，移除 `AGENT_MEMORY_BACKEND=memory` 分支（测试用 mock/内存可在测试层隔离）。

---

## 3. 数据模型（新增 2 表，改造 1 表）

### 3.1 `agent_llms`（LLM 配置，平台级，超管维护）

| 列 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| name | str(100) unique | 显示名，如 "DeepSeek-V4" |
| provider | str(30) | openai / azure / anthropic / ollama（走 `LLMFactory` 注册表） |
| model | str(100) | 模型名 |
| base_url | str 可空 | openai 兼容服务地址等 |
| api_key | str 可空 | 存储原始值；**任何响应回显掩码**（ollama 等本地可空） |
| temperature | float | 默认 0.3 |
| max_tokens | int | 默认 2048 |
| timeout | int | LLM 单次请求超时秒数，默认 60 |
| enabled | bool | 停用后不可再被新建 Agent 选用（已有会话不受影响） |
| remark | str 可空 | |
| created_by | FK users.id | |

### 3.2 `agent_definitions`（用户自建 Agent）

| 列 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| user_id | FK users.id | 归属人（超管可看全部） |
| name | str(100) | Agent 名称 |
| description | str/text 可空 | |
| llm_id | FK agent_llms.id | 选用哪个平台 LLM |
| system_prompt | text | **用户直接输入的文字提示词**；可为空串（空则 LangChain 内部默认行为） |
| tools | JSON list[str] | 默认 `[]`；用户勾选如 `["calculator","search"]` |
| enabled | bool 默认 true | 停用后不可再建新会话 |

### 3.3 `agent_conversations`（改造）

| 列 | V1 | V2 |
|---|---|---|
| agent_key | preset key | **删除** |
| model | 冗余快照 | 保留（由 agent 的 LLM 回填展示用） |
| agent_id | - | **新增** FK → agent_definitions.id（存量数据为 NULL → 只读历史、禁止续聊） |
| config_snapshot | - | **新增** JSON：`{agent_id, agent_name, llm_id, provider, model, base_url, system_prompt, tools, hash, agent_updated_at}` |
| hash | - | 单独冗余列便于查询比对（或仅存快照内，二选一，实施取一） |

**hash 算法**：`md5(f"{llm_id}:{provider}:{model}:{base_url}:{system_prompt}:{sorted(tools)}")`（api_key 不参与，避免轮换 Key 导致会话失效）。

### 3.4 记忆表（LangGraph PG Checkpointer 自带）

- 由 `langgraph-checkpoint-postgres` 的 `saver.setup()` 自动建表（`langgraph_checkpoint*`），无需手写迁移；在启动/首建 Agent 时初始化。
- 连接串：复用 `DATABASE_URL`，driver 由 `postgresql+asyncpg` 转 `postgresql+psycopg`（agent.invoke 在线程池同步执行）。

---

## 4. 后端改造点

### 4.1 配置与依赖（`app/config.py` / `.env` / `requirements.txt`）

- **删除**：`AGENT_LLM_PROVIDER/MODEL/BASE_URL/API_KEY/TEMPERATURE/MAX_TOKENS/TIMEOUT/SYSTEM_PROMPT/TOOLS_ENABLED/MEMORY_BACKEND/CHECKPOINT_DB_URI`。
- **保留**：`AGENT_ENABLED`（总开关）、`AGENT_INVOKE_TIMEOUT`（默认 180）。
- **新增依赖**：`langgraph-checkpoint-postgres`（写入 requirements）。

### 4.2 运行时（`app/agent/runtime.py` 重构）

| 现状 | 改造 |
|---|---|
| 进程级唯一 `_agent` 单例 | **多实例缓存**：`dict[agent_def_id] -> {graph, hash}`（LRU 上限如 32，超限淘汰最旧）；`threading.Lock` 双检保护 |
| `LLMFactory.create(cfg...)` 来自 env | 由 DB 的 `agent_llms` 行驱动：`LLMFactory.create(provider=..., model=..., base_url=..., api_key=..., temperature=..., max_tokens=..., timeout=...)` |
| `get_system_prompt(cfg.system_prompt)` 模板映射 | 直接用 `agent_def.system_prompt`（空串不传 system_prompt） |
| `registry.get_enabled(cfg.tools_enabled)` | `registry.get_enabled(agent_def.tools)`（空列表=纯对话） |
| memory：InMemorySaver | 固定 `PostgresSaver`（进程级共享实例；`setup()` 初始化） |
| invoke/reset/drain 由 service 分别调用，全局 ledger 并发有串扰 | runtime 提供 `run_round(agent, input, config) -> (result, records)`：**全局 asyncio 锁内** `reset_round() → invoke(线程池+超时) → ledger.drain()` 一气呵成，保证账本归属正确（PG saver 单连接亦因此安全） |
| `available_tools()` | 保留（返回注册表全部工具供 Agent 管理页勾选），由前端/服务端按勾选过滤 |

### 4.3 服务层（`agent_service.py`）

- 新增 `AgentLlmService`（LLM CRUD：掩码输出、超管校验、被引用禁止删除→409 建议禁用）。
- 新增 `AgentDefService`（Agent CRUD：owner 校验/超管放行、llm 存在且 enabled 校验、tools 白名单校验）。
- `AgentService`：
  - `create_conversation(agent_id)` → 写入 agent_id + 配置快照 + hash；`agent_key/model` 相关逻辑移除。
  - `send_message`：发送前比对会话 hash 与当前 agent hash → 不一致抛 `409（配置已变更，请新建会话继续）`；改用 `runtime.run_round(...)`。
  - 会话列表/详情：join 快照展示 agent 名称与模型标签（无需现查 LLM）。
  - 会话删除/消息/统计逻辑不变。

### 4.4 路由与 Schema（`app/api/v1/agent.py` / `schemas/agent.py`）

**LLM（新增）**
- `GET /agent/llms`（登录即可，超管+普通用户都能列选；含 enabled 过滤参数）
- `GET /agent/llms/{id}`（登录即可，key 掩码）
- `POST /agent/llms`、`PUT /agent/llms/{id}`、`DELETE /agent/llms/{id}`（`agent:llm:manage` + 后端强制 `is_superuser`）

**Agent（新增）**
- `GET /agent/agents`（本人；超管 `?all=1` 看全部含归属人）
- `GET /agent/agents/{id}`、`POST`、`PUT`、`DELETE`（owner 或超管）

**会话/消息（改造）**
- `POST /agent/conversations`：body 改 `{agent_id, title?}`；删除 `agent_key/model`
- **删除** `GET /agent/presets`
- `GET /agent/tools` 保留（供 Agent 管理页展示可勾选工具）
- 其余（列表/详情/编辑/删除/历史/发送/Token 统计）路径不变

### 4.5 权限与种子（`scripts/seed_data.py`）

- 新增权限：`agent:llm:manage`（仅 admin）、`agent:agent:manage`（admin+user）。
- 菜单「AI 助手」目录下 children 调整：
  - **LLM 配置** `/agent/llms`（`agent:llm:manage`，仅超管可见）
  - **Agent 管理** `/agent/agents`（`agent:agent:manage`，admin+user）
  - **Agent 对话** `/agent/chat`（`agent:chat`，admin+user）
- `_ensure_agent_module(db)` 幂等更新：补权限/菜单/按钮 + role 授权（增量执行已有 DB 直接补）。
- **不预置任何 LLM/Agent 业务数据**。

### 4.6 权限矩阵

| 能力 | admin(超管) | user(普通) |
|---|---|---|
| 查看/选择 LLM（列表掩码） | ✅ | ✅ |
| 创建/编辑/启停 LLM | ✅ | ❌(403) |
| 建/改/删自己 Agent | ✅ | ✅（本人） |
| 看/管全部 Agent | ✅ | ❌ |
| 新建/发送/查会话消息 | ✅ | ✅（agent:chat） |
| 删除会话 | ✅ | ❌（agent:delete，仅超管） |
| Token 统计 | ✅ | ❌（agent:stats，仅超管） |

---

## 5. 前端改造点

| 文件/位置 | 内容 |
|---|---|
| `src/api/agent.js` | 新增 `agentLlm` CRUD、`agentDef` CRUD；改造会话创建 `createAgentConversation({agent_id})`；删除 presets 调用；`getAgentTools` 保留 |
| 新建 `src/pages/agent/LlmManage.vue` | 表格+表单：name/provider/model/base_url/**api_key(不回显，编辑留空=不改)**/temperature/max_tokens/timeout/enabled/remark；新增/编辑/删除按钮挂 `v-permission="'agent:llm:manage'"` |
| 新建 `src/pages/agent/AgentManage.vue` | 卡片/表格：名称/描述/LLM 下拉(取 `/agent/llms`)/**system_prompt textarea（placeholder 示例，无模板）**/**tools 多选（默认不勾，options 取 `/agent/tools`）**/enabled；user 只见自己，超管可 `?all` 并显示归属人 |
| 改 `src/pages/agent/Chat.vue` | "新建对话"下拉由 preset 改为**我的 Agent 列表**；会话头显示 agent 名+LLM 模型 tag；空提示引导去 Agent 管理创建 |
| `src/router/index.js` | 新增静态路由 `agent/llms`、`agent/agents` |
| `src/layouts/MainLayout.vue` | iconMap 补注册 `ApiOutlined`、`ToolOutlined`（防图标丢失 bug） |

---

## 6. 测试与验证

- 更新 `backend/tests/test_agent.py`（沿用 mock `runtime.run_round/invoke_async`，不真调 LLM）：
  1. 未登录 401 / `AGENT_ENABLED=false` 503（不变）
  2. **LLM**：超管创建/编辑/删除；普通用户 POST LLM → 403；列表 key 掩码；被 Agent 引用禁止删除 → 409
  3. **Agent**：userA 建（选 LLM）；userB 列表不可见/get 404；超管 `all` 可见；未选工具默认 `[]`
  4. **会话**：选 agent 建会话带快照；发送（mock）历史/自动命名/409 归档照旧
  5. **快照守卫**：改 agent 提示词/工具后旧会话发送 → 409"配置已变更"
- 迁移与种子：`alembic` 增量 + `python -m scripts.seed_data` 幂等验证。
- 运行时冒烟：真实 PG Checkpointer 建表 + 多 Agent 构建缓存命中/淘汰日志。

---

## 7. 实施顺序（确认后执行）

1. 依赖：`requirements.txt` + 安装 `langgraph-checkpoint-postgres`（沙箱外 or 临时 venv 验证）
2. 迁移：`0005_add_agent_llm_and_definition.py`（建 2 表 + conversation 加列/去 agent_key + 存量置空）
3. 数据模型/Schema/服务/路由改造 + config/.env 清理
4. runtime 多实例缓存 + `run_round` 串行 + PG Checkpointer
5. seed 权限/菜单更新
6. 前端：api → LlmManage.vue → AgentManage.vue → Chat.vue → 路由/图标
7. 测试更新并回归（project/testcase/agent）
8. 联调验收（含 API Key 掩码与 .env 清理确认）

---

## 8. 影响与注意点

- **旧会话**（V1 数据）：`agent_id=NULL`，仅历史可见，不可续聊。
- **Agent 被改**：旧会话 409 提示新建（快照保留，历史可查）。
- **LLM 被禁用/删除**：已有会话不受影响（快照）；新建被拒。
- **API Key**：所有列表/详情回显掩码；编辑时空值表示不修改。
- **Checkpoint 表**：首次启动自动 `setup()`；多 worker 下 PG Saver 天然可用。
- 文档 `Agent模块设计文档.md` 在方案确认执行后同步修订为 V2。
