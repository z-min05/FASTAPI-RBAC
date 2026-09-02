"""Agent 运行时总开关与超时配置（LLM/Agent 业务配置已全部入库，不再依赖 env）。"""

from __future__ import annotations

import dataclasses

from app.config import settings


@dataclasses.dataclass(frozen=True)
class AgentRuntimeConfig:
    enabled: bool
    invoke_timeout: int


def get_agent_config() -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        enabled=settings.AGENT_ENABLED,
        invoke_timeout=settings.AGENT_INVOKE_TIMEOUT,
    )
