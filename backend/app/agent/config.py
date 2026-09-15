"""Agent 运行时总开关 / 超时 / bash 工作目录解析（LLM/Agent 业务配置已全部入库）。

工作目录规则：
- 顶层目录由 `settings.agent_workspace_root` 决定（未配置时取 backend/agent_workspaces）；
- 每个 Agent 一个独立子目录 `user_<用户ID>/agent_<AgentID>`，创建 Agent 时自动创建；
- 用户无需（也不能）指定路径，DB 里存的 `workspace` 只是相对顶层目录的子路径。
"""

from __future__ import annotations

import dataclasses
import pathlib

from app.config import settings
from app.utils.logger import logger


@dataclasses.dataclass(frozen=True)
class AgentRuntimeConfig:
    enabled: bool
    invoke_timeout: int
    llm_max_retries: int
    llm_retry_initial_delay: float
    llm_retry_max_delay: float


def get_agent_config() -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        enabled=settings.AGENT_ENABLED,
        invoke_timeout=settings.AGENT_INVOKE_TIMEOUT,
        llm_max_retries=settings.AGENT_LLM_MAX_RETRIES,
        llm_retry_initial_delay=settings.AGENT_LLM_RETRY_INITIAL_DELAY,
        llm_retry_max_delay=settings.AGENT_LLM_RETRY_MAX_DELAY,
    )


def workspace_root() -> pathlib.Path:
    """bash 工具顶层工作目录（沙箱根），不存在时创建。"""
    root = pathlib.Path(settings.agent_workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def agent_workspace_rel(user_id: int, agent_id: int) -> str:
    """Agent 的工作目录（相对顶层目录）"""
    return f"user_{user_id}/agent_{agent_id}"


def agent_workspace_path(user_id: int, agent_id: int) -> pathlib.Path:
    """Agent 的工作目录绝对路径，不存在时创建。"""
    path = workspace_root() / agent_workspace_rel(user_id, agent_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_agent_workspace(workspace: str | None, user_id: int, agent_id: int) -> pathlib.Path:
    """把 DB 里的相对工作目录解析为顶层目录下的绝对路径。

    - 库中值为空（存量数据未回填）时，退回按 id 推导的默认目录；
    - 值为绝对路径或越出顶层目录（如被手工改成 `../..`）时同样退回默认目录并告警，
      避免 bash 跑到顶层目录之外执行。
    """
    default = agent_workspace_path(user_id, agent_id)
    rel = (workspace or "").strip()
    if not rel:
        return default

    root = workspace_root()
    candidate = (root / rel.replace("\\", "/")).resolve()
    if candidate == root or root not in candidate.parents:
        logger.warning(
            "Agent %s 的工作目录越出顶层目录，已回退默认目录: %s", agent_id, workspace
        )
        return default

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate
