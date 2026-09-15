# Python 环境管理模块 设计文档

> 目标：新增「Python 环境管理」模块，底层基于 **Miniconda**（已由使用者自行安装）。提供虚拟环境的**增删查改**；创建时选择 Python 版本，保存后异步执行 conda 创建指令；环境路径由**配置文件**给定并写入数据库；删除时"实际环境 + 数据库记录"一并清理，失败**回滚**到一致状态。由于 conda 指令耗时较长，所有涉及 conda 的动作一律**异步**：接口先返回 `创建中 / 删除中 / 同步中`，由使用者后续刷新查看结果。

---

## 1. 现状梳理与复用点

| 能力 | 位置 | 复用方式 |
|---|---|---|
| 统一响应体 | `Response.success/error`（[response.py L5-L17](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/core/response.py#L5-L17)） | 全部接口直接复用 |
| 分页 | `PaginationParams` + `paginate`（[pagination.py L12-L104](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/core/pagination.py#L12-L104)） | 列表接口复用 |
| 通用仓储 | `BaseRepository`（[base.py L9-L52](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/repositories/base.py#L9-L52)） | 复用 `get_by_id/create/update/delete` |
| 模型基类 | `BaseModel`（[base.py L10-L20](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/models/base.py#L10-L20)） | 自带 `id/created_at/updated_at` |
| **异步后台任务范式** | `dispatch_project_sync` + `_running_tasks` 强引用（[testcase_sync_service.py L154-L170](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/testcase_sync_service.py#L154-L170)） | **本模块异步化的直接模板** |
| **子进程执行范式** | `asyncio.create_subprocess_exec` + `asyncio.wait_for` + `proc.kill()`（[auto_exec_service.py L84-L151](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/auto_exec_service.py#L84-L151)） | conda 命令执行照此实现 |
| 独立会话（后台任务用） | `AsyncSessionLocal`（[session.py L12-L16](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/db/session.py#L12-L16)） | 后台任务**必须**自建会话，不复用请求会话 |
| 下拉选项接口范式 | `GET /wecom-robots/options`（[wecom_robots.py L15-L22](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/api/v1/wecom_robots.py#L15-L22)） | 环境下拉接口照此实现 |
| 权限/菜单种子 | `scripts/seed_data.py` 的 `_ensure_*_module` | 新增 `_ensure_python_env_module` |

**关键现状**：`projects.python_path`（[project.py L16](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/models/project.py#L16)）是自动化用例执行时用的解释器路径（[plan_service.py L505-L509](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/plan_service.py#L505-L509)）。本模块产出的 `python_path` 恰好可作为该字段的取值来源 → 提供**联动选项接口**（见 §8.5）。

---

## 2. 配置文件新增项

`app/config.py` 的 `Settings` 与 `backend/.env` 同步新增（沿用现有分组注释风格）：

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `CONDA_ENABLED` | bool | `False` | 总开关；关闭时所有接口返回 403，前端隐藏菜单。与 `AGENT_ENABLED` 同风格 |
| `CONDA_HOME` | str \| None | `None` | Miniconda 安装根目录（用于推导 conda 可执行文件）**用户已安装，需在 `.env` 填写** |
| `CONDA_EXE` | str \| None | `None` | conda 可执行文件显式路径；**优先于** `CONDA_HOME` 推导 |
| `CONDA_ENV_ROOT` | str | `""` | **虚拟环境存放根目录**；环境路径 = `CONDA_ENV_ROOT/<name>`。为空视为未配置 |
| `CONDA_CMD_TIMEOUT` | int | `600` | 单条 conda 命令超时（秒）；首次创建可能数分钟 |
| `CONDA_PYTHON_VERSIONS` | str | `"3.9,3.10,3.11,3.12"` | 可选的 Python 版本列表（逗号分隔），供创建时下拉 |

同步在 `.env` 中补齐：

```ini
# Python 环境管理（Miniconda）
CONDA_ENABLED=true
CONDA_HOME=D:/miniconda3
CONDA_EXE=
CONDA_ENV_ROOT=D:/conda_envs
CONDA_CMD_TIMEOUT=600
CONDA_PYTHON_VERSIONS=3.9,3.10,3.11,3.12
```

**conda 可执行文件解析规则**（`Settings` 增加 `conda_exe` 只读属性）：

```
CONDA_EXE 非空                       → 直接使用
否则 CONDA_HOME + (Windows ? Scripts\conda.exe : bin/conda)
```

解析结果不存在 → `BadRequestException("conda 可执行文件不存在，请检查 CONDA_HOME/CONDA_EXE 配置")`。

---

## 3. 数据模型

### 3.1 新表 `python_envs`（迁移 `0006_python_envs.py`）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | int | PK | |
| `name` | String(100) | **unique**, not null | 环境名，同时作为目录名；**创建后不可改** |
| `python_version` | String(20) | not null | 如 `3.11`；**创建后不可改** |
| `env_path` | String(500) | **unique**, not null | 环境根路径，来自 `CONDA_ENV_ROOT/<name>` |
| `python_path` | String(500) | not null | 解释器路径，供 `projects.python_path` 直接引用 |
| `status` | String(20) | not null, default `pending`, index | 见 §4 状态机 |
| `error_msg` | Text | null | 失败原因（面向使用者，简明） |
| `last_output` | Text | null | 最近一次 conda 命令输出摘要（截断 2000 字，便于排查） |
| `last_synced_at` | DateTime | null | 最近一次与磁盘同步校验时间 |
| `description` | Text | null | 备注（**唯一可改字段**） |
| `created_by` | int | FK `users.id` ON DELETE SET NULL | 创建人 |
| `created_at` / `updated_at` | DateTime | not null | 继承 `BaseModel` |

以下字段归属 `BaseModel`（[base.py](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/models/base.py)），不再重复声明。

### 3.2 迁移

`alembic/versions/0006_python_envs.py`，`down_revision = "0005_plan_agent_push"`（[0005](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/alembic/versions/0005_plan_agent_push.py#L11-L12)）。`upgrade` 建表 + 唯一索引；`downgrade` 删表。

### 3.3 路径推导（不使用 conda 的 envs 目录）

统一使用 `conda create -p <path>`（**prefix 模式**）而非 `-n`，原因：

1. 环境路径完全由 `CONDA_ENV_ROOT` 决定 → 满足"路径从配置文件获取"；
2. 不污染 Miniconda 自带的 `envs` 目录；
3. 路径可精确落库，删除时无需再解析 conda 元数据。

```
env_path    = <CONDA_ENV_ROOT>/<name>
python_path = Windows ? <env_path>\python.exe : <env_path>/bin/python
```

> **注意**：`-p` 创建的环境默认**不一定**出现在 `conda env list` 中（取决于 `envs_dirs`）。因此一致性校验以**文件系统为准**（见 §5.3），`conda env list --json` 仅作辅助信息，不作为唯一判据。

---

## 4. 状态机

```
                 ┌──────────┐
   创建请求 ────► │ pending  │  记录已入库，等待后台任务
                 └────┬─────┘
                      │ 后台任务启动
                 ┌────▼─────┐
                 │ creating │  conda create 执行中
                 └────┬─────┘
         成功 ┌───────┴────────┐ 失败
        ┌─────▼────┐      ┌────▼────┐
        │  ready   │      │ failed  │◄──── 失败原因写入 error_msg
        └──┬────┬──┘      └────┬────┘
           │    │              │
  同步校验 │    │ 删除请求      │ 删除请求（允许清理失败残留）
           │    │              │
     ┌─────▼────▼──────────────▼─────┐
     │         deleting              │  (记录保留，环境删除中)
     └───────────────┬───────────────┘
            成功     │     失败
        ┌────────────▼───┐   │
        │ 记录被物理删除  │   └──► 回滚为删除前状态 + error_msg
        │ (列表刷新即消失)│
        └────────────────┘

   ready ──同步发现磁盘环境不存在──► lost（记录保留，供使用者决定删除）
   ready ──同步执行中──► syncing ──► ready / lost
```

| 状态 | 含义 | 前端展示 |
|---|---|---|
| `pending` | 已提交，等待后台任务 | 蓝 · 排队中 |
| `creating` | conda 创建中 | 蓝 · 创建中（转圈） |
| `ready` | 可用 | 绿 · 可用 |
| `failed` | 创建失败 | 红 · 失败（hover 显示 `error_msg`） |
| `syncing` | 与磁盘同步校验中 | 蓝 · 校验中 |
| `lost` | DB 有记录但磁盘环境已不存在 | 橙 · 环境丢失 |
| `deleting` | 删除中断 | 蓝 · 删除中 |

**进行中状态集合**（前端据此决定是否轮询 / 禁用操作按钮）：`{pending, creating, syncing, deleting}`。

---

## 5. 核心流程

### 5.1 创建（异步）

```
POST /python-envs
  ↓ 同步段（请求内，快）
  1. CONDA_ENABLED / CONDA_ENV_ROOT 已配置校验
  2. name 格式校验（^[A-Za-z0-9_-]{1,50}$）
  3. python_version ∈ CONDA_PYTHON_VERSIONS
  4. name / env_path 唯一性校验（DB 唯一索引兜底）
  5. 磁盘冲突校验：env_path 目录已存在 → ConflictException
  6. 落库 status=pending，commit
  7. dispatch_env_create(env_id)
  ↓ 立即返回 { id, status: "pending", ... }   ◄── 前端提示"创建中，请稍后刷新"
  ─────────────────────────────────────────
  后台任务 _create_env_task(env_id)：
  a. 独立 AsyncSessionLocal，条件更新 status=pending→creating（防重复认领）
  b. conda create -y -p <env_path> python=<version>
  c. 成功 → status=ready，回写 env_path / python_path
     失败/超时 → status=failed，写 error_msg + last_output
  d. 全程 try/except 记录日志，绝不抛出到事件循环
```

**条件更新认领**（沿用项目既有"多 worker 安全"约定）：

```sql
UPDATE python_envs SET status='creating'
WHERE id=:id AND status='pending'   -- 影响行数=0 说明已被其他任务认领，直接退出
```

### 5.2 删除（异步 + 一致性回滚）

```
DELETE /python-envs/{id}
  ↓ 同步段
  1. 记录存在校验
  2. status ∈ 进行中集合 → ConflictException("当前状态不可删除，请稍后重试")
  3. status 置 deleting（记下 prev_status），commit
  4. dispatch_env_delete(env_id, prev_status)
  ↓ 立即返回 { status: "deleting" }
  ─────────────────────────────────────────
  后台任务 _delete_env_task(env_id, prev_status)：
  以【先真环境、后数据库】为原则，分三种结果处理：
  a. conda env remove -y -p <env_path> 成功
       → 同一事务内删除 DB 记录；成功即结束（列表刷新后记录消失）
       → DB 删除抛异常：rollback，status 回滚 prev_status + error_msg
         （宁可留记录，也不留"记录已删但环境还在"的脏数据）
  b. conda 报"环境不存在"（幂等场景）→ 视为已删除，继续执行 a 的 DB 删除
  c. conda 失败/超时 → 不删 DB，status 回滚 prev_status + error_msg + last_output
       （使用者可重试；不做 `rmtree` 暴力删目录，避免误删）
```

> **关于"原子操作"的说明（重要）**：实际环境在**文件系统/conda**、记录在 **PostgreSQL**，二者跨系统，物理上无法做到真正的分布式原子提交。本设计的做法是**状态机 + 补偿回滚**：
> - DB 侧单条操作始终在**同一事务**内（`flush` → `commit`，异常 `rollback`）；
> - 跨系统侧通过"先环境后记录"的**固定顺序**把不一致窗口收敛到"记录存在但环境已删"这一种可自愈情形（同步校验会标为 `lost`）；
> - 任何一步失败都把 `status` 回滚到删除前的稳定态，保证**不会出现"记录显示 ready 但环境已不存在"**的静默错误。

### 5.3 查询 / 同步校验（异步）

列表查询走 DB，本身很快；慢的是 **conda 侧的真实状态核对**，故单独提供同步接口：

```
POST /python-envs/{id}/sync    单条
POST /python-envs/sync-all     全量
  ↓ status=ready/failed/lost → syncing，commit，立即返回
  ─────────────────────────────────────────
  后台任务 _sync_env_task(...)：
  对每条记录：
    1. 文件系统判据：env_path 目录存在？解释器文件存在？   ◄── 主判据
    2. 辅助：conda env list --json（拿不到不影响结论）
    3. 目录+解释器均在   → ready
       目录不存在       → lost（若原为 failed 则保持 failed，不升级为 lost）
    4. 写 last_synced_at
```

`last_synced_at` + 「刷新」按钮即可满足"增删查都慢 → 先返回进行中、后续刷新看结果"的诉求。

---

## 6. conda 命令规范

| 动作 | 命令 | 说明 |
|---|---|---|
| 创建 | `conda create -y -p <env_path> python=<version>` | `-y` 免交互 |
| 删除 | `conda env remove -y -p <env_path>` | 幂等：报"不存在"按成功处理 |
| 校验（辅助） | `conda env list --json` | 仅辅助，不作唯一判据 |

执行实现要点（照搬 [auto_exec_service.py L106-L131](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/backend/app/services/auto_exec_service.py#L106-L131) 的成熟写法）：

```python
proc = await asyncio.create_subprocess_exec(
    conda_exe, *args,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
raw, _ = await asyncio.wait_for(proc.communicate(), timeout=settings.CONDA_CMD_TIMEOUT)
```

- 超时 → `proc.kill()` → 按失败处理并写 `error_msg`；
- 输出经 `_strip_ansi` 去色后截断存入 `last_output`；
- `FileNotFoundError` → 明确提示 conda 路径配置错误；
- **Windows 注意**：`asyncio.create_subprocess_exec` 需 Proactor 事件循环（Python 3.8+ Windows 默认即是）。现有自动化执行已在用同一写法，故沿用即可。

---

## 7. 并发与幂等

| 场景 | 策略 |
|---|---|
| 同名重复创建 | DB `unique(name)` + 创建前校验 → `ConflictException` |
| 同路径重复创建 | DB `unique(env_path)` + 磁盘目录存在性校验 |
| 重复下发同一任务 | `status` 条件更新认领（影响行数为 0 即退出） |
| 并发删除同一条 | 删除前置状态校验：非稳定态（含 `deleting`）直接 409 |
| 删除一个已被手工删除的环境 | conda 报"不存在" → 按成功处理，继续删记录 |
| 重复点击删除 | 第二次因 `status=deleting` 被拒 |
| 多 worker 部署 | 不使用进程级共享状态；认领/状态流转全部落 DB（符合项目既有约定） |

---

## 8. API 设计

前缀 `/api/v1/python-envs`，全部返回统一 `Response` 结构。权限依赖使用 `require_permissions`（系统管理模块，JWT）。

### 8.1 列表
```
GET /python-envs?page=1&page_size=10&keyword=&status=
权限：python-env:list
返回：{ items: [...], total, page, page_size, total_pages }
```

### 8.2 详情（前端轮询单条用）
```
GET /python-envs/{id}        权限：python-env:list
```

### 8.3 新增
```
POST /python-envs
body: { name: str, python_version: str, description?: str }
权限：python-env:create
返回：{ id, name, python_version, env_path, python_path, status: "pending", ... }
message: "创建任务已提交，请稍后刷新查看结果"
```

### 8.4 编辑（仅备注）
```
PUT /python-envs/{id}
body: { description?: str }
权限：python-env:update
```
> `name` / `python_version` 创建后不可改：名称即目录名，改动会与实际路径失配；如需换版本请删除后重建。

### 8.5 下拉选项（供项目管理选解释器）
```
GET /python-envs/options     权限：仅登录（require_permissions 之外的 get_current_active_user，与 wecom-robots/options 一致）
返回：[{ id, name, python_version, python_path }]   ← 仅 status=ready
```
> 该接口**不挂 `CONDA_ENABLED` 开关**：项目管理页会无条件调用它，若返回 403 会弹出无意义的"没有操作权限"提示；未启用或无可用环境时返回空列表即可。

### 8.5.1 Python 版本列表（创建弹窗用）
```
GET /python-envs/versions    权限：仅登录 + CONDA_ENABLED
返回：{ versions: ["3.9", "3.10", "3.11", "3.12"] }   ← 来自 CONDA_PYTHON_VERSIONS 静态列表
```

### 8.6 删除
```
DELETE /python-envs/{id}     权限：python-env:delete
返回：{ status: "deleting" } / message: "删除任务已提交，请稍后刷新查看结果"
```

### 8.7 同步校验
```
POST /python-envs/{id}/sync       权限：python-env:sync
POST /python-envs/sync-all        权限：python-env:sync
返回：{ status: "syncing" }
```

### 8.8 状态驱动的响应约定

| 请求 | 同步返回 | 后续查看 |
|---|---|---|
| 创建 | `pending` | 刷新列表 / 详情 → `creating` → `ready` / `failed` |
| 删除 | `deleting` | 刷新列表 → 记录**消失**即成功；仍在则看 `error_msg` |
| 同步 | `syncing` | 刷新 → `ready` / `lost` |

---

## 9. 权限 / 菜单 / 角色

在 `scripts/seed_data.py` 新增（幂等，沿用 `_ensure_wecom_module` 的写法）：

```
PYTHON_ENV_PERMISSIONS = [
    {"name": "Python 环境列表", "code": "python-env:list",   "module": "python_env", "action": "list"},
    {"name": "新增 Python 环境", "code": "python-env:create", "module": "python_env", "action": "create"},
    {"name": "更新 Python 环境", "code": "python-env:update", "module": "python_env", "action": "update"},
    {"name": "删除 Python 环境", "code": "python-env:delete", "module": "python_env", "action": "delete"},
    {"name": "同步 Python 环境", "code": "python-env:sync",   "module": "python_env", "action": "sync"},
]
```

- 菜单为一级目录「环境管理」（`/env`，图标 `ToolOutlined`）下的二级菜单：`/env/python-envs`，图标 `CodeOutlined`，`permission=python-env:list`；
- 按钮：新增 / 编辑 / 删除 / 同步；
- 角色授权：`admin` 全量；`user` 仅 `:list`。

> 接口级开关：`CONDA_ENABLED=false` 时统一返回 `ForbiddenException("Python 环境管理未启用")`，与 Agent 模块的 `require_agent_enabled` 同思路。

---

## 10. 前端设计

### 10.1 新增文件
- `frontend/src/api/pythonEnv.js`（照 [wecomRobot.js](file:///d:/Users/zhangzhimin/Desktop/test01/fastapi-rbac/FASTAPI-RBAC/frontend/src/api/wecomRobot.js) 写法）
- `frontend/src/pages/PythonEnvManage.vue`
- `frontend/src/router/index.js` 增加 `env/python-envs` 路由

### 10.2 列表页
列：`名称 | Python 版本 | 环境路径 | 解释器路径 | 状态 | 创建人 | 创建时间 | 操作`

- 顶部：关键字搜索、状态筛选、**刷新**按钮、新增按钮；
- 状态用 `a-tag` 着色（§4 表格）；`failed` 悬浮显示 `error_msg`；`ready/lost` 显示上次校验时间；
- 操作：编辑（备注）、同步、删除（`a-popconfirm` 二次确认）；
- **进行中状态自动轮询**：当列表存在 `{pending, creating, syncing, deleting}` 的记录时，每 5s 自动拉取一次；全部进入稳定态后自动停止。页面隐藏（`visibilitychange`）时暂停。
- 路径列提供复制按钮，便于直接粘贴到项目配置。

### 10.3 创建弹窗
- 字段：环境名称（必填，`^[A-Za-z0-9_-]{1,50}$`）、Python 版本（下拉，取自 `CONDA_PYTHON_VERSIONS`）、备注；
- 提示文案：`保存后将异步执行 conda 创建，可能需要数分钟，请稍后刷新查看结果`；
- 提交成功 → 关闭弹窗 + 提示 + 列表定位到新记录（状态"排队中"）。

### 10.4 编辑弹窗
仅"备注"可编辑，其余只读展示（附提示：名称/版本创建后不可修改）。

---

## 11. 实施清单（文件级）

**后端**
1. `backend/app/config.py`：新增 6 个 `CONDA_*` 配置 + `conda_exe` 属性
2. `backend/.env`：同步配置项
3. `backend/app/models/python_env.py`：新建模型
4. `backend/app/schemas/python_env.py`：`Create / Update`（响应沿用 `to_response` 字典，与 `wecom_robot.py` 同约定）
5. `backend/app/services/python_env_service.py`：CRUD + 状态机 + 三个后台任务 + conda 执行封装
6. `backend/app/api/v1/python_envs.py`：9 个接口（含 `/options` `/versions`）
7. `backend/app/api/v1/__init__.py`：注册路由
8. `backend/alembic/versions/0006_python_envs.py`：迁移
9. `backend/scripts/seed_data.py`：`_ensure_python_env_module`（权限/菜单/按钮/授权）

**前端**
10. `frontend/src/api/pythonEnv.js`
11. `frontend/src/pages/PythonEnvManage.vue`
12. `frontend/src/router/index.js`

---

## 12. 边界与风险

| 风险 | 处理 |
|---|---|
| conda 首次创建耗时长（可达数分钟） | 异步 + `CONDA_CMD_TIMEOUT=600` 兜底；前端不阻塞 |
| conda 命令超时 | kill 进程，`status=failed` + `error_msg`，可重试 |
| 环境被手工删除 | 同步校验 → `lost`，由使用者决定删除记录 |
| 环境被占用导致删除失败 | 不删 DB、回滚状态 + 报错，支持重试；**不**暴力 `rmtree` |
| 进程重启中断进行中任务 | 记录停留在 `creating/deleting`；由同步接口或将来的启动自检复位（本期先提供手动"同步"复位） |
| Windows / POSIX 路径差异 | 解释器路径按平台分支（`python.exe` vs `bin/python`） |
| `-p` 环境不出现在 `conda env list` | 一致性判定以**文件系统**为主判据 |
| 多 worker | 认领与状态流转落 DB，不用进程级变量 |
| 数据库记录删除后前端 404 | 前端轮询 `deleting` 时把 404 视为"删除完成"并刷新列表 |

---

## 13. 验收要点

1. 未配置 `CONDA_ENV_ROOT` / conda 不可执行时，接口返回明确错误，不产生脏记录。
2. 创建：保存后立即返回 `pending`，随后列表可看到 `creating → ready`，`env_path` / `python_path` 与 `CONDA_ENV_ROOT` 规则一致且落库。
3. 删除：返回 `deleting`，稍后刷新记录消失；磁盘上对应目录同时不存在。
4. 删除失败（人为制造 conda 失败）：记录**保留**，状态回滚且 `error_msg` 可读，环境未丢失。
5. 同步：手工删除磁盘目录后执行同步 → 状态变 `lost`；恢复后同步 → 回到 `ready`。
6. 并发：重复点击创建/删除被 409 拒绝；同名创建被拒。
7. 权限：`user` 角色仅能列表；无对应权限的按钮不可见。
8. 版本下拉、路径复制、状态着色与轮询按 §10 表现。

---

## 14. 待确认项

1. `CONDA_ENV_ROOT` 与 `CONDA_HOME` 的实际路径（需写入 `.env`；当前设计假定用户本机 Miniconda 已装且路径固定）。
2. Python 版本来源：本期用**配置文件静态列表**；若需"真实可选版本"，可后续增加 `conda search python` 异步刷新接口（较慢，需缓存）。
3. 是否需要与「项目管理」联动（在下拉中直接选本模块的 `python_path` 写入 `projects.python_path`）；本设计已预留 `GET /python-envs/options` 接口。
