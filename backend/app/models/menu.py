from sqlalchemy import String, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Menu(BaseModel):
    __tablename__ = "menus"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    component: Mapped[str | None] = mapped_column(String(200), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    menu_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="目录/菜单/按钮")
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    permission: Mapped[str | None] = mapped_column(String(100), nullable=True)

    roles = relationship("Role", secondary="role_menus", back_populates="menus", lazy="noload")
