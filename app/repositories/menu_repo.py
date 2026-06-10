from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.menu import Menu
from app.repositories.base import BaseRepository


class MenuRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(Menu, db)

    async def get_by_parent_id(self, parent_id: int | None) -> list[Menu]:
        stmt = select(Menu).where(Menu.parent_id == parent_id).order_by(Menu.sort)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_menus(self) -> list[Menu]:
        stmt = select(Menu).order_by(Menu.sort)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
