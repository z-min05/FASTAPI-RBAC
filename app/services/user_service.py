from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.models.user import User
from app.security import get_password_hash
from app.schemas.user import UserCreate, UserUpdate
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import NotFoundException, ConflictException


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def get_user(self, user_id: int) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户不存在")
        return user

    async def get_users(self, params: PaginationParams) -> PaginatedResponse:
        return await self.user_repo.get_paginated(params)

    async def create_user(self, data: UserCreate) -> User:
        if await self.user_repo.get_by_username(data.username):
            raise ConflictException("用户名已存在")
        if await self.user_repo.get_by_email(data.email):
            raise ConflictException("邮箱已存在")

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=get_password_hash(data.password),
            nickname=data.nickname,
            phone=data.phone,
            department_id=data.department_id,
        )
        user = await self.user_repo.create(user)

        if data.role_ids:
            await self.user_repo.set_user_roles(user.id, data.role_ids)

        return await self.user_repo.get_by_id(user.id)

    async def update_user(self, user_id: int, data: UserUpdate) -> User:
        update_data = data.model_dump(exclude_unset=True, exclude={"role_ids"})
        user = await self.user_repo.update(user_id, update_data)
        if not user:
            raise NotFoundException("用户不存在")

        if data.role_ids is not None:
            await self.user_repo.set_user_roles(user_id, data.role_ids)

        return await self.user_repo.get_by_id(user_id)

    async def delete_user(self, user_id: int) -> None:
        if not await self.user_repo.delete(user_id):
            raise NotFoundException("用户不存在")

    async def reset_password(self, user_id: int, new_password: str) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户不存在")
        user.hashed_password = get_password_hash(new_password)
        await self.db.flush()
