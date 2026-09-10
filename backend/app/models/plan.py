from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class TestPlan(BaseModel):
    """测试计划：归属某个项目，用于组织一次测试执行"""
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 计划状态：not_started(未开始)/in_progress(进行中)/completed(已完成)
    status: Mapped[str] = mapped_column(String(20), default="not_started", nullable=False)
    # 绑定的企业微信群机器人 id 数组（推送测试结果统计）
    robot_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # 绑定的 AI 结果汇总 Agent（保存计划时自动创建会话）
    agent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_definitions.id", ondelete="SET NULL"), nullable=True
    )
    # 保存计划时创建的 Agent 会话（一个计划唯一绑定一个会话，用于执行完成后 AI 汇总）
    agent_conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_conversations.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
