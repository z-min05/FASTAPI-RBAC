from sqlalchemy import String, Boolean, Integer, Text
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
    auto_root_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    python_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    testcases = relationship("TestCase", back_populates="project", lazy="noload")
