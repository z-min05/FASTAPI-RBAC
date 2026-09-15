from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Project(BaseModel):
    """项目：用例按项目划分的容器"""
    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 自动化根路径（pytest 的 tests 目录）：由代码包初始化任务自动推导写入，不由用户填写
    auto_root_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    python_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ---------- 自动化代码初始化状态 ----------
    code_init_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none", index=True
    )
    code_init_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_init_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_init_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    code_init_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    testcases = relationship("TestCase", back_populates="project", lazy="noload")

