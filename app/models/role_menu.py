from sqlalchemy import Table, Column, Integer, ForeignKey
from app.models.base import Base

role_menus = Table(
    "role_menus",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
    Column("menu_id", Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False),
)
