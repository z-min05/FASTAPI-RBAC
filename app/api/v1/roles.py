from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse
from app.services.role_service import RoleService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.get("", summary="获取角色列表")
async def get_roles(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("role:list")),
):
    service = RoleService(db)
    result = await service.get_roles(params)
    return Response.success(data=result.model_dump())


@router.get("/{role_id}", summary="获取角色详情")
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("role:detail")),
):
    service = RoleService(db)
    role = await service.get_role(role_id)
    return Response.success(data=RoleResponse.model_validate(role).model_dump())


@router.post("", summary="创建角色")
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("role:create")),
):
    service = RoleService(db)
    role = await service.create_role(data)
    return Response.success(data=RoleResponse.model_validate(role).model_dump())


@router.put("/{role_id}", summary="更新角色")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("role:update")),
):
    service = RoleService(db)
    role = await service.update_role(role_id, data)
    return Response.success(data=RoleResponse.model_validate(role).model_dump())


@router.delete("/{role_id}", summary="删除角色")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("role:delete")),
):
    service = RoleService(db)
    await service.delete_role(role_id)
    return Response.success(message="删除成功")
