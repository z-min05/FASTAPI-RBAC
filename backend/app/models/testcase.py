from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class TestCase(BaseModel):
    """测试用例：归属某个项目，按模块划分"""
    __tablename__ = "testcases"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    module: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="P1", nullable=False)
    case_type: Mapped[str] = mapped_column(String(30), default="function", nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    precondition: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    tags: Mapped[str | None] = mapped_column(String(200), nullable=True)
    module_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    case_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    project = relationship("Project", back_populates="testcases", lazy="noload")
