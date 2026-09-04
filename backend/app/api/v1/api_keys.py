from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.models.role import Role
from app.schemas.api_key import ApiKeyCreate, ApiKeyStatusUpdate, ApiKeyResponse, ApiKeyCreatedResponse, ApiKeyRegenerateResponse
from app.services.api_key_service import ApiKeyService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/api-keys", tags=["API 密钥"])


@router.get("", summary="获取 API 密钥列表")
async def list_api_keys(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:list")),
):
    service = ApiKeyService(db)
    result = await service.paginate(params)
    # 响应中不暴露 key_hash
    items = [ApiKeyResponse.model_validate(item).model_dump() for item in result.items]
    return Response.success(data={
        "items": items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


@router.get("/roles", summary="获取可选角色列表（供创建密钥时选择）")
async def list_roles_for_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:list")),
):
    result = await db.execute(select(Role.id, Role.name))
    roles = [{"id": r.id, "name": r.name} for r in result.all()]
    return Response.success(data=roles)


@router.post("", summary="创建 API 密钥")
async def create_api_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:create")),
):
    service = ApiKeyService(db)
    api_key, full_key = await service.create(data, current_user.id)
    resp = ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(api_key).model_dump(),
        full_key=full_key,
    )
    return Response.success(data=resp.model_dump())


@router.put("/{key_id}/status", summary="启用/禁用 API 密钥")
async def update_api_key_status(
    key_id: int,
    data: ApiKeyStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:update")),
):
    service = ApiKeyService(db)
    api_key = await service.update_status(key_id, data.is_active)
    return Response.success(
        message="已启用" if api_key.is_active else "已禁用",
        data=ApiKeyResponse.model_validate(api_key).model_dump(),
    )


@router.delete("/{key_id}", summary="删除 API 密钥")
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:delete")),
):
    service = ApiKeyService(db)
    await service.delete(key_id)
    return Response.success(message="删除成功")


@router.post("/{key_id}/regenerate", summary="重新生成密钥")
async def regenerate_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:update")),
):
    service = ApiKeyService(db)
    _, full_key = await service.regenerate(key_id)
    return Response.success(data=ApiKeyRegenerateResponse(full_key=full_key).model_dump())