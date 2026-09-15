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
    # bash 工具的工作目录：相对顶层工作目录的子路径（user_<用户ID>/agent_<AgentID>），
    # 由服务端创建 Agent 时自动分配，顶层目录见 AGENT_WORKSPACE_ROOT
    workspace: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
