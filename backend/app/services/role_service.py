from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.role_repo import RoleRepository
from app.models.role import Role
from app.models.user_role import user_roles
from app.schemas.role import RoleCreate, RoleUpdate
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.casbin_service import invalidate_policy
from app.exceptions import NotFoundException, ConflictException


class RoleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.role_repo = RoleRepository(db)

    async def get_role(self, role_id: int) -> Role:
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")
        return role

    async def get_roles(self, params: PaginationParams) -> PaginatedResponse:
        return await self.role_repo.get_paginated(params)

    async def create_role(self, data: RoleCreate) -> Role:
        if await self.role_repo.get_by_code(data.code):
            raise ConflictException("角色编码已存在")

        role = Role(
            name=data.name,
            code=data.code,
            description=data.description,
            sort=data.sort,
            is_active=data.is_active,
        )
        role = await self.role_repo.create(role)

        if data.permission_ids:
            await self.role_repo.set_role_permissions(role.id, data.permission_ids)
        if data.menu_ids:
            await self.role_repo.set_role_menus(role.id, data.menu_ids)

        return await self.role_repo.get_by_id(role.id)

    async def update_role(self, role_id: int, data: RoleUpdate) -> Role:
        update_data = data.model_dump(exclude_unset=True, exclude={"permission_ids", "menu_ids"})
        role = await self.role_repo.update(role_id, update_data)
        if not role:
            raise NotFoundException("角色不存在")

        need_invalidate = data.permission_ids is not None or data.menu_ids is not None
        if data.permission_ids is not None:
            await self.role_repo.set_role_permissions(role_id, data.permission_ids)
        if data.menu_ids is not None:
            await self.role_repo.set_role_menus(role_id, data.menu_ids)

        if need_invalidate:
            await self._invalidate_role_users(role_id)

        return await self.role_repo.get_by_id(role_id)

    async def delete_role(self, role_id: int) -> None:
        if not await self.role_repo.delete(role_id):
            raise NotFoundException("角色不存在")
        await self._invalidate_role_users(role_id)

    async def _invalidate_role_users(self, role_id: int) -> None:
        """清除该角色下所有用户的 Casbin 策略缓存"""
        await invalidate_policy(self.db)
