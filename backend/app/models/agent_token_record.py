from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AgentTokenRecord(BaseModel):
    """Agent Token 消耗记录：模型调用计费/统计明细（审计保留，删除会话时不级联）"""
    __tablename__ = "agent_token_records"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_conversations.id"), index=True, nullable=True
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)
