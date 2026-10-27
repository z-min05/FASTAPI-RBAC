from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ApiKey(BaseModel):
    """API 密钥：归属某个用户，权限与归属用户完全一致"""
    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="密钥名称/描述")
    key_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True, comment="密钥哈希值"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="密钥前缀（前8位），用于显示识别"
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True,
        comment="归属用户：密钥的权限与操作归属均跟随该用户"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="过期时间，NULL 表示永不过期"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后使用时间"
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
