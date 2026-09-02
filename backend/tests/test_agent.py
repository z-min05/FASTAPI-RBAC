"""Agent（AI 助手）模块 V2 黑盒接口测试。

V2 模型：LLM 配置（平台级，超管维护）-> 用户自建 Agent（选 LLM/提示词/工具）-> 会话（配置快照+hash 守卫）。

约定（与 project/testcase 测试一致）：
- 未登录 401；功能开关关闭 503；
- Agent 开关依赖通过 dependency_overrides 放行；
- 涉及普通用户走需权限接口时，monkeypatch check_api_permission 放行（避免依赖 Casbin 种子）；
- 发送消息时 monkeypatch runtime.run_round，避免真实调用大模型。
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient

CONV_URL = "/api/v1/agent/conversations"
LLM_URL = "/api/v1/agent/llms"
AGENT_URL = "/api/v1/agent/agents"
TOOLS_URL = "/api/v1/agent/tools"


# ==================== fixtures ====================


@pytest_asyncio.fixture
async def agent_enabled():
    """放行 /agent 接口的功能开关依赖 require_agent_enabled。"""
    from app.api.v1.agent import require_agent_enabled
    from app.main import app

    app.dependency_overrides[require_agent_enabled] = lambda: True
    yield
    app.dependency_overrides.pop(require_agent_enabled, None)


@pytest_asyncio.fixture
async def grant_perms(monkeypatch):
    """放行 Casbin API 权限校验（普通用户可访问需权限接口）。"""
    import app.dependency as dep

    async def _always_true(user_id, permission):
        return True

    monkeypatch.setattr(dep, "check_api_permission", _always_true)
    yield


@pytest_asyncio.fixture
async def mock_run_round(monkeypatch):
    """将 runtime.run_round 替换为本地假实现（记录调用并返回固定回复，无 token 记录）。"""
    from app.agent import runtime as agent_runtime

    calls = []

    async def _fake_run_round(spec, input_data, config):
        calls.append({"spec": spec, "input": input_data, "config": config})
        user_text = input_data["messages"][-1]["content"]
        return (
            {
                "messages": [
                    SimpleNamespace(type="user", content=user_text),
                    SimpleNamespace(type="ai", content="模拟回复：你好"),
                ]
            },
            [],
        )

    monkeypatch.setattr(agent_runtime, "run_round", _fake_run_round)
    return calls


async def _register_user(client: AsyncClient, username: str) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "test123456",
    })
    assert resp.status_code == 200, resp.text
    from sqlalchemy import select
    from app.models.user import User
    from app.security import create_access_token
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}


async def _make_headers(client: AsyncClient, username: str, is_superuser: bool = False) -> dict:
    headers = await _register_user(client, username)
    if is_superuser:
        from sqlalchemy import select
        from app.models.user import User
        from tests.conftest import TestSessionLocal

        async with TestSessionLocal() as session:
            user = (await session.execute(select(User).where(User.username == username))).scalar_one()
            user.is_superuser = True
            await session.commit()
    return headers


async def _create_llm(client: AsyncClient, headers: dict, name: str = "测试LLM", **extra) -> dict:
    payload = {
        "name": name,
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test-1234567890abcdef",
        "temperature": 0.3,
        "max_tokens": 2048,
        "timeout": 60,
        "enabled": True,
    }
    payload.update(extra)
    resp = await client.post(LLM_URL, headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _create_agent(client: AsyncClient, headers: dict, llm_id: int, name: str = "测试Agent", **extra) -> dict:
    payload = {
        "name": name,
        "description": "用于接口测试",
        "llm_id": llm_id,
        "system_prompt": "你是一个测试助手",
        "tools": [],
        "enabled": True,
    }
    payload.update(extra)
    resp = await client.post(AGENT_URL, headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _create_conversation(client: AsyncClient, headers: dict, agent_id: int, **extra) -> dict:
    resp = await client.post(CONV_URL, headers=headers, json={"agent_id": agent_id, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _make_env(client: AsyncClient, headers: dict, agent_name: str = "测试Agent") -> dict:
    """超管：LLM + Agent 环境，返回 llm/agent。"""
    llm = await _create_llm(client, headers)
    agent = await _create_agent(client, headers, llm["id"], name=agent_name)
    return {"llm": llm, "agent": agent}


# ==================== 基础开关 ====================


@pytest.mark.asyncio
async def test_agent_unauthorized(client: AsyncClient):
    """未登录访问 Agent 接口应返回 401"""
    resp = await client.get(CONV_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_agent_disabled_returns_503(client: AsyncClient, superuser_headers: dict, monkeypatch):
    """AGENT_ENABLED=false 时接口应返回 503"""
    from app.config import settings

    monkeypatch.setattr(settings, "AGENT_ENABLED", False)
    resp = await client.get(CONV_URL, headers=superuser_headers)
    assert resp.status_code == 503


# ==================== LLM 配置 ====================


@pytest.mark.asyncio
async def test_llm_crud_flow(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """超管：LLM 新增/列表掩码/详情/更新/删除全流程"""
    data = await _create_llm(client, superuser_headers)
    llm_id = data["id"]
    # api_key 不回显、掩码展示
    assert "api_key" not in data
    assert data["api_key_mask"].startswith("sk-") and "****" in data["api_key_mask"]
    assert data["enabled"] is True

    # 列表
    resp = await client.get(LLM_URL, headers=superuser_headers, params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] >= 1
    item = next(x for x in body["items"] if x["id"] == llm_id)
    assert "api_key" not in item and item["api_key_mask"]

    # 详情
    resp = await client.get(f"{LLM_URL}/{llm_id}", headers=superuser_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["model"] == "gpt-4o-mini"

    # 更新模型与 api_key
    resp = await client.put(
        f"{LLM_URL}/{llm_id}", headers=superuser_headers,
        json={"model": "gpt-4o", "api_key": "sk-new-abcdef9876543210"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["model"] == "gpt-4o"

    # 名称唯一冲突
    resp = await client.post(LLM_URL, headers=superuser_headers, json={
        "name": "测试LLM", "provider": "openai", "model": "x",
    })
    assert resp.status_code == 409

    # 删除（无引用）
    resp = await client.delete(f"{LLM_URL}/{llm_id}", headers=superuser_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_llm_normal_user_readonly(client: AsyncClient, superuser_headers: dict, auth_headers: dict, agent_enabled, grant_perms):
    """普通用户可查看 LLM（掩码），但不能增删改"""
    await _create_llm(client, superuser_headers)

    # 可查看
    resp = await client.get(LLM_URL, headers=auth_headers, params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    # 创建被拒 403
    resp = await client.post(LLM_URL, headers=auth_headers, json={
        "name": "非法创建", "provider": "openai", "model": "x",
    })
    assert resp.status_code == 403

    # 更新/删除被拒 403
    llm_id = resp.json().get("data", {})
    resp = await client.put(f"{LLM_URL}/1", headers=auth_headers, json={"model": "y"})
    assert resp.status_code == 403
    resp = await client.delete(f"{LLM_URL}/1", headers=auth_headers)
    assert resp.status_code == 403


# ==================== Agent 定义 ====================


@pytest.mark.asyncio
async def test_agent_crud_flow(client: AsyncClient, superuser_headers: dict, agent_enabled, mock_run_round):
    """超管：Agent 新增/列表/详情/更新/删除全流程"""
    env = await _make_env(client, superuser_headers)
    agent = env["agent"]

    # 列表（mine 默认只返回本人）
    resp = await client.get(AGENT_URL, headers=superuser_headers, params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert any(x["id"] == agent["id"] for x in body["items"])
    item = next(x for x in body["items"] if x["id"] == agent["id"])
    assert item["llm_name"] and item["llm_model"] == "gpt-4o-mini"
    assert item["tools"] == [] and item["enabled"] is True

    # 详情
    resp = await client.get(f"{AGENT_URL}/{agent['id']}", headers=superuser_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["system_prompt"] == "你是一个测试助手"

    # 更新提示词/工具/停用
    resp = await client.put(
        f"{AGENT_URL}/{agent['id']}", headers=superuser_headers,
        json={"system_prompt": "新的提示词", "enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False

    # 删除（无会话引用）
    resp = await client.delete(f"{AGENT_URL}/{agent['id']}", headers=superuser_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_agent_tool_whitelist(client: AsyncClient, superuser_headers: dict, agent_enabled, monkeypatch):
    """Agent 只能勾选注册表内工具，非法工具 400"""
    from app.agent import runtime as agent_runtime

    monkeypatch.setattr(agent_runtime, "list_tool_names", lambda: ["calculator"])
    llm = await _create_llm(client, superuser_headers)

    resp = await client.post(AGENT_URL, headers=superuser_headers, json={
        "name": "非法工具Agent", "llm_id": llm["id"], "tools": ["not-exist-tool"],
    })
    assert resp.status_code == 400

    resp = await client.post(AGENT_URL, headers=superuser_headers, json={
        "name": "合法工具Agent", "llm_id": llm["id"], "tools": ["calculator"],
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["tools"] == ["calculator"]


@pytest.mark.asyncio
async def test_agent_ownership(client: AsyncClient, superuser_headers: dict, agent_enabled, grant_perms):
    """Agent 可见性：用户只见自己的；跨用户访问 403；超管 scope=all 可见全部"""
    admin = await _make_env(client, superuser_headers)

    user1 = await _make_headers(client, "user1")
    user2 = await _make_headers(client, "user2")
    llm = admin["llm"]  # LLM 平台级共享，复用 admin 的配置
    agent1 = await _create_agent(client, user1, llm["id"], name="用户1的Agent")
    agent2 = await _create_agent(client, user2, llm["id"], name="用户2的Agent")

    # user1 列表只见自己的
    resp = await client.get(AGENT_URL, headers=user1, params={"page": 1, "page_size": 20})
    ids = [x["id"] for x in resp.json()["data"]["items"]]
    assert agent1["id"] in ids and agent2["id"] not in ids

    # user1 访问 user2 的 Agent -> 403
    resp = await client.get(f"{AGENT_URL}/{agent2['id']}", headers=user1)
    assert resp.status_code == 403
    resp = await client.put(f"{AGENT_URL}/{agent2['id']}", headers=user1, json={"name": "篡改"})
    assert resp.status_code == 403
    resp = await client.delete(f"{AGENT_URL}/{agent2['id']}", headers=user1)
    assert resp.status_code == 403

    # 超管 scope=all 可见全部
    resp = await client.get(AGENT_URL, headers=superuser_headers, params={"scope": "all", "page_size": 20})
    ids_all = [x["id"] for x in resp.json()["data"]["items"]]
    assert agent1["id"] in ids_all and agent2["id"] in ids_all
    # admin 自己创建在列表中
    assert admin["agent"]["id"] in ids_all


@pytest.mark.asyncio
async def test_llm_delete_blocked_when_referenced(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """被 Agent 引用的 LLM 删除应 409"""
    env = await _make_env(client, superuser_headers)
    resp = await client.delete(f"{LLM_URL}/{env['llm']['id']}", headers=superuser_headers)
    assert resp.status_code == 409

    # 删除 Agent 后可删除 LLM
    resp = await client.delete(f"{AGENT_URL}/{env['agent']['id']}", headers=superuser_headers)
    assert resp.status_code == 200
    resp = await client.delete(f"{LLM_URL}/{env['llm']['id']}", headers=superuser_headers)
    assert resp.status_code == 200


# ==================== 会话 ====================


@pytest.mark.asyncio
async def test_conversation_crud(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """会话：基于 Agent 创建（快照）/列表/详情/编辑/删除"""
    env = await _make_env(client, superuser_headers)

    data = await _create_conversation(client, superuser_headers, env["agent"]["id"])
    conv_id = data["id"]
    assert data["agent_id"] == env["agent"]["id"]
    assert data["title"] == "新对话"
    assert data["model"] == "gpt-4o-mini"

    # 列表带出 agent 名称（来自快照）
    resp = await client.get(CONV_URL, headers=superuser_headers, params={"page": 1, "page_size": 10})
    body = resp.json()["data"]
    item = next(x for x in body["items"] if x["id"] == conv_id)
    assert item["agent_id"] == env["agent"]["id"]
    assert item["agent_name"] == "测试Agent"

    # 详情
    resp = await client.get(f"{CONV_URL}/{conv_id}", headers=superuser_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["agent_name"] == "测试Agent"

    # 编辑标题
    resp = await client.put(f"{CONV_URL}/{conv_id}", headers=superuser_headers, json={"title": "接口联调会话"})
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "接口联调会话"

    # 删除
    resp = await client.delete(f"{CONV_URL}/{conv_id}", headers=superuser_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_conversation_requires_own_agent(client: AsyncClient, superuser_headers: dict, agent_enabled, grant_perms):
    """不能使用他人 Agent 创建会话（403）"""
    env = await _make_env(client, superuser_headers)  # superadmin 的 Agent
    other = await _make_headers(client, "otheruser")
    llm = env["llm"]
    # superadmin 再建一个 Agent，otheruser 拿不到 id 权限即可验证
    agent = await _create_agent(client, superuser_headers, llm["id"], name="共享Agent")

    resp = await client.post(CONV_URL, headers=other, json={"agent_id": agent["id"]})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_delete_blocked_when_conversations(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """被会话引用的 Agent 删除应 409"""
    env = await _make_env(client, superuser_headers)
    await _create_conversation(client, superuser_headers, env["agent"]["id"])
    resp = await client.delete(f"{AGENT_URL}/{env['agent']['id']}", headers=superuser_headers)
    assert resp.status_code == 409


# ==================== 消息发送 ====================


@pytest.mark.asyncio
async def test_send_message_flow(client: AsyncClient, superuser_headers: dict, agent_enabled, mock_run_round):
    """发送消息：spec 组装正确 + 落库 + 自动命名 + 回复 + 无 token 记录"""
    env = await _make_env(client, superuser_headers)
    data = await _create_conversation(client, superuser_headers, env["agent"]["id"])
    conv_id = data["id"]

    long_first_message = "这是一条超过二十个字符的首条消息，用于验证会话标题的自动截断逻辑是否正确。"
    resp = await client.post(
        f"{CONV_URL}/{conv_id}/messages",
        headers=superuser_headers,
        json={"content": long_first_message},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["reply"] == "模拟回复：你好"
    assert body["token"]["call_count"] == 0
    assert body["assistant_message_id"]

    # spec 组装：agent_id / llm 配置 / 提示词 / 工具
    call = mock_run_round[0]
    assert call["spec"]["agent_id"] == env["agent"]["id"]
    assert call["spec"]["llm"]["model"] == "gpt-4o-mini"
    assert call["spec"]["llm"]["api_key"] == "sk-test-1234567890abcdef"
    assert call["spec"]["system_prompt"] == "你是一个测试助手"
    assert call["config"]["configurable"]["thread_id"].startswith("conv-")

    # 自动命名截断为前 20 字符
    resp = await client.get(f"{CONV_URL}/{conv_id}", headers=superuser_headers)
    assert resp.json()["data"]["title"] == long_first_message[:20]

    # 消息历史升序 user + assistant
    resp = await client.get(f"{CONV_URL}/{conv_id}/messages", headers=superuser_headers)
    items = resp.json()["data"]["items"]
    assert [m["role"] for m in items] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_send_message_token_accounting(client: AsyncClient, superuser_headers: dict, agent_enabled, monkeypatch):
    """发送成功时 token 记录落库并返回统计，stats 汇总生效"""
    from app.agent import runtime as agent_runtime

    async def _token_run_round(spec, input_data, config):
        rec = SimpleNamespace(
            model="gpt-4o-mini", step=1, input_tokens=12, output_tokens=8,
            total_tokens=20, tool_calls=[],
        )
        return (
            {"messages": [
                SimpleNamespace(type="user", content=input_data["messages"][-1]["content"]),
                SimpleNamespace(type="ai", content="带记账的回复"),
            ]},
            [rec],
        )

    monkeypatch.setattr(agent_runtime, "run_round", _token_run_round)

    env = await _make_env(client, superuser_headers)
    conv = await _create_conversation(client, superuser_headers, env["agent"]["id"])
    resp = await client.post(
        f"{CONV_URL}/{conv['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["token"] == {"call_count": 1, "total_input": 12, "total_output": 8, "total_tokens": 20}

    # assistant 消息带 token_total
    resp = await client.get(f"{CONV_URL}/{conv['id']}/messages", headers=superuser_headers)
    assistant = resp.json()["data"]["items"][-1]
    assert assistant["role"] == "assistant" and assistant["token_total"] == 20

    # stats 汇总
    resp = await client.get("/api/v1/agent/stats/tokens", headers=superuser_headers)
    summary = resp.json()["data"]["summary"]
    assert summary["call_count"] == 1 and summary["total_tokens"] == 20
    assert summary["by_model"][0]["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_send_message_config_changed_conflict(client: AsyncClient, superuser_headers: dict, agent_enabled, mock_run_round):
    """Agent 配置变更后旧会话发送应 409（快照守卫）"""
    env = await _make_env(client, superuser_headers)
    conv = await _create_conversation(client, superuser_headers, env["agent"]["id"])

    # 修改提示词（配置指纹变化）
    resp = await client.put(
        f"{AGENT_URL}/{env['agent']['id']}", headers=superuser_headers,
        json={"system_prompt": "修改后的提示词"},
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"{CONV_URL}/{conv['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 409
    assert "配置已变更" in resp.json()["message"]

    # 新建会话后可正常继续
    conv2 = await _create_conversation(client, superuser_headers, env["agent"]["id"])
    resp = await client.post(
        f"{CONV_URL}/{conv2['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_send_message_llm_disabled_conflict(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """Agent 或 LLM 停用后旧会话发送应 409"""
    env = await _make_env(client, superuser_headers)
    conv = await _create_conversation(client, superuser_headers, env["agent"]["id"])

    # 停用 Agent
    resp = await client.put(
        f"{AGENT_URL}/{env['agent']['id']}", headers=superuser_headers, json={"enabled": False}
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"{CONV_URL}/{conv['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 409
    assert "已停用" in resp.json()["message"]


@pytest.mark.asyncio
async def test_send_message_timeout(client: AsyncClient, superuser_headers: dict, agent_enabled, monkeypatch):
    """AI 处理超时应返回 400 并提示超时"""
    from app.agent import runtime as agent_runtime

    async def _boom(spec, input_data, config):
        raise agent_runtime.AgentInvokeError("timeout", timed_out=True)

    monkeypatch.setattr(agent_runtime, "run_round", _boom)

    env = await _make_env(client, superuser_headers)
    conv = await _create_conversation(client, superuser_headers, env["agent"]["id"])
    resp = await client.post(
        f"{CONV_URL}/{conv['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 400
    assert "超时" in resp.json()["message"]


@pytest.mark.asyncio
async def test_send_message_invoke_error(client: AsyncClient, superuser_headers: dict, agent_enabled, monkeypatch):
    """AI 推理失败应返回 400 通用错误"""
    from app.agent import runtime as agent_runtime

    async def _boom(spec, input_data, config):
        raise agent_runtime.AgentInvokeError("boom")

    monkeypatch.setattr(agent_runtime, "run_round", _boom)

    env = await _make_env(client, superuser_headers)
    conv = await _create_conversation(client, superuser_headers, env["agent"]["id"])
    resp = await client.post(
        f"{CONV_URL}/{conv['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 400
    assert "失败" in resp.json()["message"]


@pytest.mark.asyncio
async def test_send_message_archived_conflict(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """向已归档会话发送消息应返回 409"""
    env = await _make_env(client, superuser_headers)
    conv = await _create_conversation(client, superuser_headers, env["agent"]["id"])

    resp = await client.put(
        f"{CONV_URL}/{conv['id']}", headers=superuser_headers, json={"status": "archived"}
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"{CONV_URL}/{conv['id']}/messages",
        headers=superuser_headers,
        json={"content": "ping"},
    )
    assert resp.status_code == 409


# ==================== 能力 / 统计 ====================


@pytest.mark.asyncio
async def test_tools_endpoint(client: AsyncClient, superuser_headers: dict, agent_enabled, monkeypatch):
    """工具能力接口返回全部可用工具"""
    from app.agent import runtime as agent_runtime

    monkeypatch.setattr(
        agent_runtime, "available_tools",
        lambda: [{"name": "calculator", "description": "数学计算"}],
    )
    resp = await client.get(TOOLS_URL, headers=superuser_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["tools"][0]["name"] == "calculator"
    assert body["tools"][0]["description"] == "数学计算"


@pytest.mark.asyncio
async def test_token_stats_zero(client: AsyncClient, superuser_headers: dict, agent_enabled):
    """无调用时 Token 统计为零值"""
    resp = await client.get("/api/v1/agent/stats/tokens", headers=superuser_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    summary = body["summary"]
    assert summary["call_count"] == 0
    assert summary["total_tokens"] == 0
    assert summary["by_model"] == []
    assert body["recent"] == []
