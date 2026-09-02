from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.permission_repo import PermissionRepository
from app.models.permission import Permission
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.casbin_service import invalidate_policy
from app.exceptions import NotFoundException, ConflictException


class PermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.perm_repo = PermissionRepository(db)

    async def get_permission(self, perm_id: int) -> Permission:
        perm = await self.perm_repo.get_by_id(perm_id)
        if not perm:
            raise NotFoundException("权限不存在")
        return perm

    async def get_permissions(self, params: PaginationParams) -> PaginatedResponse:
        return await self.perm_repo.get_paginated(params)

    async def create_permission(self, data: PermissionCreate) -> Permission:
        if await self.perm_repo.get_by_code(data.code):
            raise ConflictException("权限编码已存在")
        perm = Permission(**data.model_dump())
        result = await self.perm_repo.create(perm)
        await invalidate_policy(self.db)
        return result

    async def update_permission(self, perm_id: int, data: PermissionUpdate) -> Permission:
        update_data = data.model_dump(exclude_unset=True)
        perm = await self.perm_repo.update(perm_id, update_data)
        if not perm:
            raise NotFoundException("权限不存在")
        await invalidate_policy(self.db)
        return perm

    async def delete_permission(self, perm_id: int) -> None:
        if not await self.perm_repo.delete(perm_id):
            raise NotFoundException("权限不存在")
        await invalidate_policy(self.db)
