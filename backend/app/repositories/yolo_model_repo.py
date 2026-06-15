from app.repositories.base import BaseRepository
from app.models.yolo_model import YoloModel
from sqlalchemy.ext.asyncio import AsyncSession


class YoloModelRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(YoloModel, db)
