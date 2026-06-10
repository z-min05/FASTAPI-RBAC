from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.permission import Permission
from app.repositories.base import BaseRepository


class PermissionRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(Permission, db)

    async def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
