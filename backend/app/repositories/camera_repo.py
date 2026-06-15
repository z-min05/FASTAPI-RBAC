from app.repositories.base import BaseRepository
from app.models.camera import Camera
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class CameraRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(Camera, db)

    async def get_by_ip(self, ip: str, port: int) -> Camera | None:
        stmt = select(Camera).where(Camera.ip == ip, Camera.port == port)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
