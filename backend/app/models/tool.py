from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Tool(BaseModel):
    """工具管理

    每个工具由「压缩包」与「README 文档」两个文件组成，文件实体存放在
    TOOL_STORAGE_DIR 下，表中只保存相对该目录的文件名（storage key），
    删除记录时按同样规则拼回真实路径并删除文件。
    """
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="工具名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="工具描述")
    package_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="压缩包原始文件名"
    )
    package_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="压缩包存储文件名（相对存储根目录）"
    )
    package_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="压缩包大小（字节）"
    )
    readme_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="README 原始文件名"
    )
    readme_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="README 存储文件名（相对存储根目录）"
    )
    readme_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="README 大小（字节）"
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
