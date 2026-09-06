from sqlalchemy import String, Text, ForeignKey
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
