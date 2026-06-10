from sqlalchemy import Table, Column, Integer, ForeignKey
from app.models.base import Base

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
)
