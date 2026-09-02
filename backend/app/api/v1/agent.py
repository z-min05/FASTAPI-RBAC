"""Agent 路由 V2：LLM 配置 + 用户自建 Agent + 会话/消息/Token 统计。

- LLM：查（agent:llm:list/detail）、增（agent:llm:create）、改（agent:llm:update）、
  删（agent:llm:delete）均按 RBAC 细粒度授权。
- Agent/会话/消息/统计：登录用户即可使用，各自数据按 user 隔离（超管可看全部）。
- 会话：创建时快照配置，Agent 变更后旧会话禁止续聊。
- 消息：普通接口一次性返回；/stream 提供 SSE 流式（文本增量 + 工具调用 + Token）。
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import runtime as agent_runtime
from app.db.session import get_db
from app.config import settings
from app.core.pagination import PaginationParams
from app.core.response import Response
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.agent import (
    AgentDefCreate,
    AgentDefUpdate,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    LlmCreate,
    LlmUpdate,
    MessageSend,
)
from app.services.agent_service import (
    AgentDefService,
    AgentLlmService,
    AgentService,
)
from app.utils.logger import logger

router = APIRouter(prefix="/agent", tags=["Agent"])


async def require_agent_enabled():
    """Agent 功能总开关（未启用时返回 503）。"""
    if not settings.AGENT_ENABLED:
        raise HTTPException(status_code=503, detail="Agent 功能未启用")
    return True


# ==================== LLM 配置（平台级） ====================


@router.get("/llms", summary="LLM 配置列表")
async def list_llms(
    params: PaginationParams = Depends(),
    enabled: bool | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(require_permissions("agent:llm:list")),
):
    service = AgentLlmService(db)
    return Response.success(
        data=await service.list_llms(params, enabled=enabled, keyword=keyword)
    )


@router.get("/llms/{llm_id}", summary="LLM 配置详情")
async def get_llm(
    llm_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(require_permissions("agent:llm:detail")),
):
    service = AgentLlmService(db)
    return Response.success(data=await service.get_llm(llm_id))


@router.post("/llms", summary="创建 LLM 配置（RBAC：agent:llm:create）")
async def create_llm(
    data: LlmCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(require_permissions("agent:llm:create")),
):
    service = AgentLlmService(db)
    return Response.success(data=await service.create(current_user, data), message="创建成功")


@router.put("/llms/{llm_id}", summary="修改 LLM 配置（RBAC：agent:llm:update）")
async def update_llm(
    llm_id: int,
    data: LlmUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(require_permissions("agent:llm:update")),
):
    service = AgentLlmService(db)
    return Response.success(data=await service.update(current_user, llm_id, data), message="更新成功")


@router.delete("/llms/{llm_id}", summary="删除 LLM 配置（RBAC：agent:llm:delete）")
async def delete_llm(
    llm_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(require_permissions("agent:llm:delete")),
):
    service = AgentLlmService(db)
    await service.delete(current_user, llm_id)
    return Response.success(message="删除成功")


# ==================== Agent 定义（用户自建） ====================


@router.get("/agents", summary="我的 Agent 列表")
async def list_agents(
    params: PaginationParams = Depends(),
    scope: str = "mine",  # superuser 可传 all
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentDefService(db)
    all_users = current_user.is_superuser and scope == "all"
    return Response.success(
        data=await service.list_agents(
            current_user.id, current_user.is_superuser, params,
            all_users=all_users, keyword=keyword,
        )
    )


@router.get("/agents/{agent_id}", summary="Agent 详情")
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentDefService(db)
    return Response.success(
        data=await service.get_agent(current_user.id, current_user.is_superuser, agent_id)
    )


@router.post("/agents", summary="创建 Agent")
async def create_agent(
    data: AgentDefCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentDefService(db)
    return Response.success(
        data=await service.create(current_user.id, data), message="创建成功"
    )


@router.put("/agents/{agent_id}", summary="修改 Agent")
async def update_agent(
    agent_id: int,
    data: AgentDefUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentDefService(db)
    return Response.success(
        data=await service.update(current_user.id, current_user.is_superuser, agent_id, data),
        message="更新成功",
    )


@router.delete("/agents/{agent_id}", summary="删除 Agent")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentDefService(db)
    await service.delete(current_user.id, current_user.is_superuser, agent_id)
    return Response.success(message="删除成功")


# ==================== 会话 ====================


@router.post("/conversations", summary="创建会话")
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    conv = await service.create_conversation(current_user.id, data)
    return Response.success(
        data=ConversationResponse.model_validate(conv).model_dump(), message="创建成功"
    )


@router.get("/conversations", summary="我的会话列表")
async def list_conversations(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    return Response.success(data=await service.list_conversations(current_user.id, params))


@router.get("/conversations/{conversation_id}", summary="会话详情")
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    conv = await service.get_conversation(current_user.id, conversation_id)
    return Response.success(data=ConversationResponse.model_validate(conv).model_dump())


@router.put("/conversations/{conversation_id}", summary="修改会话（标题/归档）")
async def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    conv = await service.update_conversation(current_user.id, conversation_id, data)
    return Response.success(data=ConversationResponse.model_validate(conv).model_dump())


@router.delete("/conversations/{conversation_id}", summary="删除会话")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    await service.delete_conversation(current_user.id, conversation_id)
    return Response.success(message="删除成功")


# ==================== 消息 ====================


@router.get("/conversations/{conversation_id}/messages", summary="会话历史消息")
async def list_messages(
    conversation_id: int,
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    return Response.success(
        data=await service.list_messages(current_user.id, conversation_id, params)
    )


@router.post("/conversations/{conversation_id}/messages", summary="发送消息")
async def send_message(
    conversation_id: int,
    data: MessageSend,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    result = await service.send_message(current_user.id, conversation_id, data.content)
    return Response.success(data=result)


# ==================== 消息（SSE 流式） ====================


def _sse_event(payload: dict) -> str:
    """序列化为 SSE data 帧。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sum_token_stats(records) -> dict:
    return {
        "input": sum(r.input_tokens for r in records),
        "output": sum(r.output_tokens for r in records),
        "total": sum(r.total_tokens for r in records),
    }


@router.post("/conversations/{conversation_id}/messages/stream", summary="发送消息（SSE 流式）")
async def stream_send_message(
    conversation_id: int,
    data: MessageSend,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    """SSE 流式回复：文本增量 / 工具调用 / 结束(含 Token 统计) / 错误。

    前置校验（归档/快照守卫等）失败时返回普通 JSON 错误；
    通过后以 text/event-stream 返回。
    """
    service = AgentService(db)
    ctx = await service.prepare_stream(current_user.id, conversation_id, data.content)

    async def event_stream():
        reply_parts: list[str] = []
        try:
            async for ev in agent_runtime.stream_round(
                ctx["spec"], ctx["input_data"], ctx["config"]
            ):
                etype = ev.get("type")
                if etype == "text":
                    reply_parts.append(ev["content"])
                    yield _sse_event({"type": "text", "content": ev["content"]})
                elif etype == "tool":
                    yield _sse_event(
                        {
                            "type": "tool",
                            "index": ev.get("index"),
                            "name": ev.get("name"),
                            "args": ev.get("args"),
                            "call_id": ev.get("call_id"),
                        }
                    )
                elif etype == "tool_result":
                    yield _sse_event(
                        {
                            "type": "tool_result",
                            "index": ev.get("index"),
                            "output": ev.get("output"),
                            "call_id": ev.get("call_id"),
                        }
                    )
                elif etype == "final":
                    reply = (
                        ev.get("reply")
                        or "".join(reply_parts)
                        or "（AI 未能生成有效回复，请重试）"
                    )
                    records = ev.get("records") or []
                    try:
                        await service.persist_stream_result(
                            current_user.id, ctx["conv_id"], reply, records
                        )
                    except Exception:
                        logger.warning("流式结果落库异常（不影响本次回复展示）", exc_info=True)
                    yield _sse_event(
                        {"type": "done", "reply": reply, "tokens": _sum_token_stats(records)}
                    )
        except agent_runtime.AgentInvokeError as exc:
            # 失败/超时：已产生的 token 记录照常落库（审计），不落 assistant 消息
            try:
                await service.persist_stream_result(
                    current_user.id, ctx["conv_id"], "", exc.records, with_message=False
                )
            except Exception:
                logger.warning("流式失败记录落库异常", exc_info=True)
            tip = "AI 处理超时，请稍后重试或缩短问题" if exc.timed_out else "AI 处理失败，请稍后重试"
            yield _sse_event({"type": "error", "message": tip})
        except Exception:
            logger.exception("流式响应异常 conv_id=%s", conversation_id)
            yield _sse_event({"type": "error", "message": "流式响应异常，请稍后重试"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== 能力 / 统计 ====================


@router.get("/tools", summary="当前可选工具")
async def get_tools(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    return Response.success(
        data={
            "tools": agent_runtime.available_tools(),
        }
    )


@router.get("/stats/tokens", summary="我的 Token 统计")
async def get_token_stats(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_agent_enabled),
    current_user: User = Depends(get_current_active_user),
):
    service = AgentService(db)
    return Response.success(
        data=await service.get_token_stats(current_user.id, params.page, params.page_size)
    )
