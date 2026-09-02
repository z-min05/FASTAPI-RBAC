from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AgentMessage(BaseModel):
    """Agent 会话消息：仅存面向用户的 user/assistant 消息，tool 内部往返不入表"""
    __tablename__ = "agent_messages"

    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
