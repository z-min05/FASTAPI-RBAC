from app.repositories.base import BaseRepository
from app.models.detection_task import DetectionTask
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class DetectionTaskRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(DetectionTask, db)

    async def get_active_tasks(self) -> list[DetectionTask]:
        stmt = select(DetectionTask).where(DetectionTask.is_active == True)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
