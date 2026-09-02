from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AgentConversation(BaseModel):
    """Agent 会话：多轮对话的容器，与 LangGraph thread_id 一一映射。

    - agent_id：关联用户自建 Agent（旧版 preset 数据为 NULL，仅保留历史）
    - config_snapshot：创建会话时的 Agent 配置快照（LLM/提示词/工具 + hash）
    - config_hash：Agent 配置指纹，发送前比对，不一致则禁止续聊
    """

    __tablename__ = "agent_conversations"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="新对话", nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    agent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_definitions.id"), index=True, nullable=True
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
