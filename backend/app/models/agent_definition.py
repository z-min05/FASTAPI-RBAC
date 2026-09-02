from sqlalchemy import String, Integer, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AgentDefinition(BaseModel):
    """用户自建 Agent：选用平台 LLM + 自填系统提示词 + 自选工具。"""

    __tablename__ = "agent_definitions"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_id: Mapped[int] = mapped_column(Integer, ForeignKey("agent_llms.id"), index=True, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tools: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
