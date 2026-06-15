from app.repositories.base import BaseRepository
from app.models.detection_result import DetectionResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class DetectionResultRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(DetectionResult, db)

    async def get_by_task_id(self, task_id: int) -> list[DetectionResult]:
        stmt = select(DetectionResult).where(DetectionResult.task_id == task_id).order_by(DetectionResult.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
