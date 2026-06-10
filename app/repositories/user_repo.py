from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.user_role import user_roles
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        # 先删除旧关联
        await self.db.execute(
            user_roles.delete().where(user_roles.c.user_id == user_id)
        )
        # 再插入新关联
        if role_ids:
            await self.db.execute(
                user_roles.insert(),
                [{"user_id": user_id, "role_id": rid} for rid in role_ids],
            )
        await self.db.flush()

    async def get_user_role_ids(self, user_id: int) -> list[int]:
        stmt = select(user_roles.c.role_id).where(user_roles.c.user_id == user_id)
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]
