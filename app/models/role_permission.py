from sqlalchemy import Table, Column, Integer, ForeignKey
from app.models.base import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
)
