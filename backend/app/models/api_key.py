from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ApiKey(BaseModel):
    """API 密钥：关联角色，权限跟随角色"""
    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="密钥名称/描述")
    key_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True, comment="密钥哈希值"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="密钥前缀（前8位），用于显示识别"
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True
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