from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.permission import PermissionCreate, PermissionUpdate, PermissionResponse
from app.services.permission_service import PermissionService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/permissions", tags=["权限管理"])


@router.get("", summary="获取权限列表")
async def get_permissions(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("permission:list")),
):
    service = PermissionService(db)
    result = await service.get_permissions(params)
    return Response.success(data=result.model_dump())


@router.get("/{perm_id}", summary="获取权限详情")
async def get_permission(
    perm_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("permission:detail")),
):
    service = PermissionService(db)
    perm = await service.get_permission(perm_id)
    return Response.success(data=PermissionResponse.model_validate(perm).model_dump())


@router.post("", summary="创建权限")
async def create_permission(
    data: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("permission:create")),
):
    service = PermissionService(db)
    perm = await service.create_permission(data)
    return Response.success(data=PermissionResponse.model_validate(perm).model_dump())


@router.put("/{perm_id}", summary="更新权限")
async def update_permission(
    perm_id: int,
    data: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("permission:update")),
):
    service = PermissionService(db)
    perm = await service.update_permission(perm_id, data)
    return Response.success(data=PermissionResponse.model_validate(perm).model_dump())


@router.delete("/{perm_id}", summary="删除权限")
async def delete_permission(
    perm_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("permission:delete")),
):
    service = PermissionService(db)
    await service.delete_permission(perm_id)
    return Response.success(message="删除成功")
