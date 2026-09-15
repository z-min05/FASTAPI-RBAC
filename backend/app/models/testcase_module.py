from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TestCaseModule(BaseModel):
    """用例模块：项目内的多级模块树

    与磁盘结构一一对应：
    - 非末级模块（有子节点）→ 一个文件夹（code 为目录名）
    - 末级模块（无子节点）→ 一个 pytest 文件（code 为文件名，需以 test_ 开头）
    """

    __tablename__ = "testcase_modules"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("testcase_modules.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # 模块名称（展示用）
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # 磁盘名：目录名，或末级模块的 pytest 文件名（不含 .py）；所有模块一律必填
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
