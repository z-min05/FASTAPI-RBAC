from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.models.base import Base


async def init_db():
    """首次启动时创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_tables():
    """创建所有表（开发用）"""
    import app.models  # noqa: F401 - 触发模型注册
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
