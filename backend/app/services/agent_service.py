"""Agent 服务层 V2：LLM 配置 + Agent 定义 + 会话/消息/Token 统计。

- LLM：平台级，仅超管可增删改；全员可查看（api_key 掩码）并选用。
- Agent：用户自建（选 LLM、自填提示词、勾选工具）；仅本人可见，超管可看全部。
- 会话：创建时快照 Agent 配置并生成 hash；发送前比对，不一致则禁止续聊。
- 运行时：通过 agent_runtime.run_round()（串行 reset/invoke/drain），账本不串扰。
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import runtime as agent_runtime
from app.agent.config import get_agent_config
from app.core.pagination import PaginationParams
from app.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.agent_conversation import AgentConversation
from app.models.agent_definition import AgentDefinition
from app.models.agent_llm import AgentLlm
from app.models.agent_message import AgentMessage
from app.models.agent_token_record import AgentTokenRecord
from app.models.user import User
from app.schemas.agent import (
    AgentDefCreate,
    AgentDefUpdate,
    ConversationCreate,
    ConversationUpdate,
    LlmCreate,
    LlmUpdate,
)
from app.utils.logger import logger


def mask_api_key(api_key: Optional[str]) -> str:
    """api_key 掩码（不回显原始值）。"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:6]}****{api_key[-4:]}"


# ==================== 配置快照与指纹 ====================


def agent_config_hash(agent: AgentDefinition, llm: AgentLlm) -> str:
    """Agent 运行配置指纹：LLM 相关字段 + 提示词 + 工具。

    api_key 不参与 hash，避免轮换密钥导致存量会话全部失效。
    """
    raw = "|".join(
        [
            str(llm.id),
            str(llm.provider or ""),
            str(llm.model or ""),
            str(llm.base_url or ""),
            str(agent.system_prompt or ""),
            json.dumps(sorted(agent.tools or []), ensure_ascii=False),
        ]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_snapshot(agent: AgentDefinition, llm: AgentLlm) -> dict:
    """会话创建时的 Agent 配置快照（用于展示与配置变更比对）。"""
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "description": agent.description,
        "llm_id": llm.id,
        "provider": llm.provider,
        "model": llm.model,
        "base_url": llm.base_url,
        "system_prompt": agent.system_prompt,
        "tools": agent.tools or [],
        "hash": agent_config_hash(agent, llm),
        "agent_updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }


def _to_paginated(items: list, total: int, params: PaginationParams) -> dict:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": math.ceil(total / params.page_size) if total > 0 else 0,
    }


def _compose_spec(agent: AgentDefinition, llm: AgentLlm, current_hash: str) -> dict:
    """组装运行时规格：LLM 配置 + 提示词 + 工具勾选。"""
    return {
        "agent_id": agent.id,
        "hash": current_hash,
        "llm": {
            "provider": llm.provider,
            "model": llm.model,
            "base_url": llm.base_url,
            "api_key": llm.api_key,
            "temperature": llm.temperature,
            "max_tokens": llm.max_tokens,
            "timeout": llm.timeout,
        },
        "system_prompt": agent.system_prompt or "",
        "tools": agent.tools or [],
    }


def _build_token_records(user_id: int, conv_id: int, records) -> list[AgentTokenRecord]:
    """把 runtime 产出的 TokenRecord 转成待落库的 ORM 记录。"""
    return [
        AgentTokenRecord(
            user_id=user_id,
            conversation_id=conv_id,
            model=r.model,
            step=r.step,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            tool_calls=",".join(r.tool_calls) if r.tool_calls else None,
        )
        for r in records
    ]


# ==================== LLM 配置 ====================


class AgentLlmService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_llm(self, llm_id: int) -> AgentLlm:
        llm = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.id == llm_id))
        ).scalar_one_or_none()
        if not llm:
            raise NotFoundException("LLM 配置不存在")
        return llm

    def _to_dict(self, llm: AgentLlm) -> dict:
        return {
            "id": llm.id,
            "name": llm.name,
            "provider": llm.provider,
            "model": llm.model,
            "base_url": llm.base_url,
            "api_key_mask": mask_api_key(llm.api_key),
            "temperature": llm.temperature,
            "max_tokens": llm.max_tokens,
            "timeout": llm.timeout,
            "enabled": llm.enabled,
            "remark": llm.remark,
            "created_at": llm.created_at.isoformat() if llm.created_at else None,
            "updated_at": llm.updated_at.isoformat() if llm.updated_at else None,
        }

    async def list_llms(
        self,
        params: PaginationParams,
        enabled: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> dict:
        conds = []
        if enabled is not None:
            conds.append(AgentLlm.enabled == enabled)
        if keyword:
            like = f"%{keyword}%"
            conds.append((AgentLlm.name.ilike(like)) | (AgentLlm.model.ilike(like)))
        total = (
            await self.db.execute(select(func.count()).select_from(AgentLlm).where(*conds))
        ).scalar() or 0
        stmt = (
            select(AgentLlm)
            .where(*conds)
            .order_by(AgentLlm.id.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return _to_paginated([self._to_dict(x) for x in rows], total, params)

    async def get_llm(self, llm_id: int) -> dict:
        return self._to_dict(await self._get_llm(llm_id))

    async def create(self, current_user: User, data: LlmCreate) -> dict:
        if not current_user.is_superuser:
            raise ForbiddenException("仅管理员可创建 LLM 配置")
        exist = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.name == data.name))
        ).scalar_one_or_none()
        if exist:
            raise ConflictException(f"LLM 名称「{data.name}」已存在")
        llm = AgentLlm(
            name=data.name,
            provider=data.provider,
            model=data.model,
            base_url=data.base_url,
            api_key=data.api_key,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            timeout=data.timeout,
            enabled=data.enabled,
            remark=data.remark,
            created_by=current_user.id,
        )
        self.db.add(llm)
        await self.db.flush()
        await self.db.refresh(llm)
        return self._to_dict(llm)

    async def update(self, current_user: User, llm_id: int, data: LlmUpdate) -> dict:
        if not current_user.is_superuser:
            raise ForbiddenException("仅管理员可修改 LLM 配置")
        llm = await self._get_llm(llm_id)
        if data.name is not None and data.name != llm.name:
            exist = (
                await self.db.execute(select(AgentLlm).where(AgentLlm.name == data.name))
            ).scalar_one_or_none()
            if exist:
                raise ConflictException(f"LLM 名称「{data.name}」已存在")
            llm.name = data.name
        if data.provider is not None:
            llm.provider = data.provider
        if data.model is not None:
            llm.model = data.model
        if data.base_url is not None:
            llm.base_url = data.base_url
        if data.api_key:
            llm.api_key = data.api_key
        if data.temperature is not None:
            llm.temperature = data.temperature
        if data.max_tokens is not None:
            llm.max_tokens = data.max_tokens
        if data.timeout is not None:
            llm.timeout = data.timeout
        if data.enabled is not None:
            llm.enabled = data.enabled
        if data.remark is not None:
            llm.remark = data.remark
        await self.db.flush()
        await self.db.refresh(llm)
        return self._to_dict(llm)

    async def delete(self, current_user: User, llm_id: int) -> None:
        if not current_user.is_superuser:
            raise ForbiddenException("仅管理员可删除 LLM 配置")
        llm = await self._get_llm(llm_id)
        ref_count = (
            await self.db.execute(
                select(func.count()).select_from(AgentDefinition).where(AgentDefinition.llm_id == llm.id)
            )
        ).scalar() or 0
        if ref_count:
            raise ConflictException(f"该 LLM 仍被 {ref_count} 个 Agent 使用，请先停用或删除相关 Agent")
        await self.db.delete(llm)
        await self.db.flush()


# ==================== Agent 定义（用户自建） ====================


class AgentDefService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_dict(agent: AgentDefinition, llm: AgentLlm | None = None, owner_name: str | None = None) -> dict:
        return {
            "id": agent.id,
            "user_id": agent.user_id,
            "owner_name": owner_name,
            "name": agent.name,
            "description": agent.description,
            "llm_id": agent.llm_id,
            "llm_name": llm.name if llm else None,
            "llm_model": llm.model if llm else None,
            "system_prompt": agent.system_prompt,
            "tools": agent.tools or [],
            "enabled": agent.enabled,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }

    async def _get_agent(self, agent_id: int) -> AgentDefinition:
        agent = (
            await self.db.execute(select(AgentDefinition).where(AgentDefinition.id == agent_id))
        ).scalar_one_or_none()
        if not agent:
            raise NotFoundException("Agent 不存在")
        return agent

    async def _check_llm_usable(self, llm_id: int) -> AgentLlm:
        llm = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.id == llm_id))
        ).scalar_one_or_none()
        if not llm:
            raise NotFoundException("所选 LLM 不存在")
        if not llm.enabled:
            raise ConflictException("所选 LLM 已停用，请先在 LLM 配置中选择其他模型")
        return llm

    async def _check_tools(self, tools: list[str]) -> None:
        """工具白名单：只允许注册表内可用工具。"""
        allowed = set(agent_runtime.list_tool_names())
        unknown = [t for t in (tools or []) if t not in allowed]
        if unknown:
            raise BadRequestException(f"不支持的工具：{', '.join(unknown)}")

    async def list_agents(
        self,
        user_id: int,
        is_superuser: bool,
        params: PaginationParams,
        all_users: bool = False,
        keyword: Optional[str] = None,
    ) -> dict:
        conds = []
        if not (is_superuser and all_users):
            conds.append(AgentDefinition.user_id == user_id)
        if keyword:
            conds.append(AgentDefinition.name.ilike(f"%{keyword}%"))

        total = (
            await self.db.execute(select(func.count()).select_from(AgentDefinition).where(*conds))
        ).scalar() or 0
        stmt = (
            select(AgentDefinition)
            .where(*conds)
            .order_by(AgentDefinition.updated_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        llm_ids = {a.llm_id for a in rows}
        llm_map: dict[int, AgentLlm] = {}
        if llm_ids:
            llm_rows = (
                await self.db.execute(select(AgentLlm).where(AgentLlm.id.in_(llm_ids)))
            ).scalars().all()
            llm_map = {x.id: x for x in llm_rows}

        items = [self._to_dict(a, llm_map.get(a.llm_id)) for a in rows]
        return _to_paginated(items, total, params)

    async def get_agent(self, user_id: int, is_superuser: bool, agent_id: int) -> dict:
        agent = await self._get_agent(agent_id)
        if agent.user_id != user_id and not is_superuser:
            raise ForbiddenException("无权访问该 Agent")
        llm = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.id == agent.llm_id))
        ).scalar_one_or_none()
        return self._to_dict(agent, llm)

    async def create(self, user_id: int, data: AgentDefCreate) -> dict:
        llm = await self._check_llm_usable(data.llm_id)
        await self._check_tools(data.tools or [])
        agent = AgentDefinition(
            user_id=user_id,
            name=data.name,
            description=data.description,
            llm_id=llm.id,
            system_prompt=data.system_prompt or "",
            tools=data.tools or [],
            enabled=True,
        )
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)
        return self._to_dict(agent, llm)

    async def update(self, user_id: int, is_superuser: bool, agent_id: int, data: AgentDefUpdate) -> dict:
        agent = await self._get_agent(agent_id)
        if agent.user_id != user_id and not is_superuser:
            raise ForbiddenException("无权修改该 Agent")
        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.system_prompt is not None:
            agent.system_prompt = data.system_prompt
        if data.tools is not None:
            await self._check_tools(data.tools)
            agent.tools = data.tools
        if data.enabled is not None:
            agent.enabled = data.enabled
        if data.llm_id is not None and data.llm_id != agent.llm_id:
            llm = await self._check_llm_usable(data.llm_id)
            agent.llm_id = llm.id
        await self.db.flush()
        await self.db.refresh(agent)
        llm = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.id == agent.llm_id))
        ).scalar_one_or_none()
        return self._to_dict(agent, llm)

    async def delete(self, user_id: int, is_superuser: bool, agent_id: int) -> None:
        agent = await self._get_agent(agent_id)
        if agent.user_id != user_id and not is_superuser:
            raise ForbiddenException("无权删除该 Agent")
        conv_count = (
            await self.db.execute(
                select(func.count())
                .select_from(AgentConversation)
                .where(AgentConversation.agent_id == agent.id)
            )
        ).scalar() or 0
        if conv_count:
            raise ConflictException(f"该 Agent 已被 {conv_count} 个会话使用，请先删除相关会话")
        await self.db.delete(agent)
        await self.db.flush()


# ==================== 会话 / 消息 ====================


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_owned(self, user_id: int, conv_id: int) -> AgentConversation:
        conv = (
            await self.db.execute(select(AgentConversation).where(AgentConversation.id == conv_id))
        ).scalar_one_or_none()
        if not conv:
            raise NotFoundException("会话不存在")
        if conv.user_id != user_id:
            raise ForbiddenException("无权访问该会话")
        return conv

    def _to_dict(self, conv: AgentConversation) -> dict:
        snap = conv.config_snapshot or {}
        return {
            "id": conv.id,
            "title": conv.title,
            "agent_id": conv.agent_id,
            "agent_name": snap.get("agent_name"),
            "model": conv.model or snap.get("model"),
            "status": conv.status,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }

    async def _load_agent_with_llm(self, conv: AgentConversation):
        """加载会话所依赖的 Agent 及其 LLM；异常时给出明确指引。"""
        if not conv.agent_id:
            raise ConflictException("该会话为旧版数据，仅支持查看历史，请新建会话继续")
        agent = (
            await self.db.execute(select(AgentDefinition).where(AgentDefinition.id == conv.agent_id))
        ).scalar_one_or_none()
        if not agent:
            raise ConflictException("会话所依赖的 Agent 已被删除，无法继续发送，请新建会话")
        if not agent.enabled:
            raise ConflictException("会话所依赖的 Agent 已停用，无法继续发送，请新建会话")
        llm = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.id == agent.llm_id))
        ).scalar_one_or_none()
        if not llm or not llm.enabled:
            raise ConflictException("会话所依赖的 LLM 已停用或删除，无法继续发送，请新建会话")
        return agent, llm

    # ------------------------------------------------------------------ #
    #  会话
    # ------------------------------------------------------------------ #

    async def create_conversation(self, user_id: int, data: ConversationCreate) -> AgentConversation:
        agent = (
            await self.db.execute(
                select(AgentDefinition).where(
                    AgentDefinition.id == data.agent_id, AgentDefinition.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if not agent:
            raise ForbiddenException("仅可使用自己的 Agent 创建会话")
        if not agent.enabled:
            raise ConflictException("该 Agent 已停用，无法创建会话")
        llm = (
            await self.db.execute(select(AgentLlm).where(AgentLlm.id == agent.llm_id))
        ).scalar_one_or_none()
        if not llm or not llm.enabled:
            raise ConflictException("该 Agent 所依赖的 LLM 已停用或删除，无法创建会话")

        conv = AgentConversation(
            user_id=user_id,
            title=(data.title or "").strip() or "新对话",
            thread_id=f"conv-{uuid.uuid4().hex}",
            agent_id=agent.id,
            model=llm.model,
            config_hash=agent_config_hash(agent, llm),
            config_snapshot=build_snapshot(agent, llm),
            status="active",
        )
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def list_conversations(self, user_id: int, params: PaginationParams) -> dict:
        base = [AgentConversation.user_id == user_id, AgentConversation.status == "active"]
        total = (
            await self.db.execute(select(func.count()).select_from(AgentConversation).where(*base))
        ).scalar() or 0
        stmt = (
            select(AgentConversation)
            .where(*base)
            .order_by(AgentConversation.updated_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return _to_paginated([self._to_dict(c) for c in items], total, params)

    async def get_conversation(self, user_id: int, conv_id: int) -> dict:
        return self._to_dict(await self._get_owned(user_id, conv_id))

    async def update_conversation(self, user_id: int, conv_id: int, data: ConversationUpdate) -> dict:
        conv = await self._get_owned(user_id, conv_id)
        if data.title is not None:
            conv.title = data.title
        if data.status is not None:
            conv.status = data.status
        await self.db.flush()
        await self.db.refresh(conv)
        return self._to_dict(conv)

    async def delete_conversation(self, user_id: int, conv_id: int) -> None:
        conv = await self._get_owned(user_id, conv_id)
        thread_id = conv.thread_id
        # 解绑 token 记录（保留审计，防止外键阻止删除）
        await self.db.execute(
            update(AgentTokenRecord)
            .where(AgentTokenRecord.conversation_id == conv.id)
            .values(conversation_id=None)
        )
        await self.db.delete(conv)
        await self.db.flush()
        # 清理引擎层记忆（PG checkpoint），失败仅告警不影响业务删除
        await agent_runtime.clear_memory(thread_id)

    # ------------------------------------------------------------------ #
    #  消息
    # ------------------------------------------------------------------ #

    async def list_messages(self, user_id: int, conv_id: int, params: PaginationParams) -> dict:
        conv = await self._get_owned(user_id, conv_id)
        base = [AgentMessage.conversation_id == conv.id]
        total = (
            await self.db.execute(select(func.count()).select_from(AgentMessage).where(*base))
        ).scalar() or 0
        stmt = (
            select(AgentMessage)
            .where(*base)
            .order_by(AgentMessage.id.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        items = [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "token_total": m.token_total,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in reversed(rows)  # 升序返回，便于聊天展示
        ]
        return _to_paginated(items, total, params)

    async def send_message(self, user_id: int, conv_id: int, content: str) -> dict:
        conv = await self._get_owned(user_id, conv_id)
        if conv.status != "active":
            raise ConflictException("会话已归档，无法继续发送")

        # 配置快照守卫：Agent（LLM/提示词/工具）变更后禁止续聊
        agent, llm = await self._load_agent_with_llm(conv)
        current_hash = agent_config_hash(agent, llm)
        if conv.config_hash and conv.config_hash != current_hash:
            raise ConflictException("Agent 配置已变更，请新建会话继续")

        # 1. 用户消息落库；首次对话自动命名
        self.db.add(AgentMessage(conversation_id=conv.id, role="user", content=content))
        if conv.title == "新对话":
            conv.title = content.strip()[:20]
        await self.db.flush()

        # 2. 构造运行规格并执行（runtime 内串行 reset/invoke/drain）
        spec = _compose_spec(agent, llm, current_hash)
        input_data = {"messages": [{"role": "user", "content": content}]}
        config = {"configurable": {"thread_id": conv.thread_id}}

        try:
            result, records = await agent_runtime.run_round(spec, input_data, config)
        except agent_runtime.AgentInvokeError as exc:
            # 失败/超时也把已产生的 token 记录落库（审计用途）
            await self._save_token_records(user_id, conv.id, exc.records)
            if exc.timed_out:
                raise BadRequestException("AI 处理超时，请稍后重试或缩短问题")
            logger.warning("Agent invoke 失败: %s", exc)
            raise BadRequestException("AI 处理失败，请稍后重试")

        reply = self._extract_reply(result)
        total_tokens = sum(r.total_tokens for r in records)
        assistant_msg = AgentMessage(
            conversation_id=conv.id,
            role="assistant",
            content=reply,
            token_total=total_tokens or None,
        )
        self.db.add(assistant_msg)
        await self.db.flush()
        await self._save_token_records(user_id, conv.id, records)

        return {
            "reply": reply,
            "token": {
                "call_count": len(records),
                "total_input": sum(r.input_tokens for r in records),
                "total_output": sum(r.output_tokens for r in records),
                "total_tokens": total_tokens,
            },
            "assistant_message_id": assistant_msg.id,
        }

    async def prepare_stream(self, user_id: int, conv_id: int, content: str) -> dict:
        """流式发送前置：权限/归档/快照守卫 + 用户消息落库并提交。

        返回运行上下文（spec/input/config 等）。提交用户消息后即可安全开启 SSE 流，
        流式期间的 DB 写入改由 persist_stream_result 用独立会话完成。
        """
        conv = await self._get_owned(user_id, conv_id)
        if conv.status != "active":
            raise ConflictException("会话已归档，无法继续发送")

        # 配置快照守卫：Agent（LLM/提示词/工具）变更后禁止续聊
        agent, llm = await self._load_agent_with_llm(conv)
        current_hash = agent_config_hash(agent, llm)
        if conv.config_hash and conv.config_hash != current_hash:
            raise ConflictException("Agent 配置已变更，请新建会话继续")

        # 用户消息落库；首次对话自动命名
        self.db.add(AgentMessage(conversation_id=conv.id, role="user", content=content))
        title_changed = False
        if conv.title == "新对话":
            conv.title = content.strip()[:20]
            title_changed = True
        await self.db.flush()
        await self.db.commit()

        return {
            "spec": _compose_spec(agent, llm, current_hash),
            "input_data": {"messages": [{"role": "user", "content": content}]},
            "config": {"configurable": {"thread_id": conv.thread_id}},
            "conv_id": conv.id,
            "title_changed": title_changed,
        }

    async def persist_stream_result(
        self,
        user_id: int,
        conv_id: int,
        reply: str,
        records,
        with_message: bool = True,
    ) -> None:
        """流式结束后用独立会话落库（assistant 消息 + token 记录）。

        请求会话在 SSE 流结束后可能已被回收，因此这里自建会话；
        会话若在流式期间被删除则跳过（避免孤儿记录）。
        """
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            conv = (
                await session.execute(
                    select(AgentConversation).where(
                        AgentConversation.id == conv_id, AgentConversation.user_id == user_id
                    )
                )
            ).scalar_one_or_none()
            if not conv:
                logger.info("会话已删除，跳过流式结果落库 conv_id=%s", conv_id)
                return
            if with_message:
                total_tokens = sum(r.total_tokens for r in records)
                session.add(
                    AgentMessage(
                        conversation_id=conv.id,
                        role="assistant",
                        content=reply or "（AI 未能生成有效回复，请重试）",
                        token_total=total_tokens or None,
                    )
                )
            session.add_all(_build_token_records(user_id, conv.id, records))
            # 触达 updated_at，让会话列表排序/刷新感知到本轮回复
            await session.execute(
                update(AgentConversation).where(AgentConversation.id == conv.id).values(updated_at=func.now())
            )
            await session.commit()

    async def _save_token_records(self, user_id: int, conv_id: int, records) -> None:
        self.db.add_all(_build_token_records(user_id, conv_id, records))
        await self.db.flush()

    @staticmethod
    def _extract_reply(result) -> str:
        """从 invoke 结果中提取最终的 AI 文本回复。"""
        messages = result.get("messages", []) if isinstance(result, dict) else []
        for msg in reversed(messages):
            if getattr(msg, "type", None) != "ai":
                continue
            content = getattr(msg, "content", "")
            if content:
                return content if isinstance(content, str) else str(content)
        return "（AI 未能生成有效回复，请重试）"

    # ------------------------------------------------------------------ #
    #  Token 统计
    # ------------------------------------------------------------------ #

    async def get_token_stats(self, user_id: int, page: int = 1, page_size: int = 10) -> dict:
        base = [AgentTokenRecord.user_id == user_id]
        row = (
            await self.db.execute(
                select(
                    func.count(AgentTokenRecord.id),
                    func.coalesce(func.sum(AgentTokenRecord.input_tokens), 0),
                    func.coalesce(func.sum(AgentTokenRecord.output_tokens), 0),
                    func.coalesce(func.sum(AgentTokenRecord.total_tokens), 0),
                ).where(*base)
            )
        ).one()
        call_count, total_input, total_output, total_tokens = row

        by_model_rows = (
            await self.db.execute(
                select(
                    AgentTokenRecord.model,
                    func.count(AgentTokenRecord.id),
                    func.coalesce(func.sum(AgentTokenRecord.input_tokens), 0),
                    func.coalesce(func.sum(AgentTokenRecord.output_tokens), 0),
                    func.coalesce(func.sum(AgentTokenRecord.total_tokens), 0),
                )
                .where(*base)
                .group_by(AgentTokenRecord.model)
            )
        ).all()

        total = (
            (
                await self.db.execute(
                    select(func.count(AgentTokenRecord.id)).where(*base)
                )
            ).scalar()
            or 0
        )
        recent_stmt = (
            select(AgentTokenRecord)
            .where(*base)
            .order_by(AgentTokenRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        recent = (await self.db.execute(recent_stmt)).scalars().all()

        return {
            "summary": {
                "call_count": call_count,
                "total_input": total_input,
                "total_output": total_output,
                "total_tokens": total_tokens,
                "by_model": [
                    {
                        "model": m,
                        "call_count": cnt,
                        "input": i,
                        "output": o,
                        "total": t,
                    }
                    for m, cnt, i, o, t in by_model_rows
                ],
            },
            "recent": {
                "items": [
                    {
                        "id": r.id,
                        "conversation_id": r.conversation_id,
                        "model": r.model,
                        "step": r.step,
                        "input_tokens": r.input_tokens,
                        "output_tokens": r.output_tokens,
                        "total_tokens": r.total_tokens,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in recent
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
