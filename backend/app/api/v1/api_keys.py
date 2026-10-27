from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyStatusUpdate, ApiKeyCreatedResponse, ApiKeyRegenerateResponse
from app.services.api_key_service import ApiKeyService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/api-keys", tags=["API 密钥"])


@router.get("", summary="获取当前用户归属的 API 密钥列表")
async def list_api_keys(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:list")),
):
    service = ApiKeyService(db)
    result = await service.paginate(params, current_user.id)
    # 响应中不暴露 key_hash
    return Response.success(data=result.model_dump())


@router.post("", summary="创建 API 密钥（归属当前用户）")
async def create_api_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:create")),
):
    service = ApiKeyService(db)
    api_key, full_key = await service.create(data, current_user)
    resp = ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        user_id=api_key.user_id,
        user_name=current_user.nickname or current_user.username,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
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
    api_key = await service.update_status(key_id, data.is_active, current_user.id)
    return Response.success(
        message="已启用" if api_key.is_active else "已禁用",
        data={
            "id": api_key.id,
            "is_active": api_key.is_active,
            "updated_at": api_key.updated_at,
        },
    )


@router.delete("/{key_id}", summary="删除 API 密钥")
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:delete")),
):
    service = ApiKeyService(db)
    await service.delete(key_id, current_user.id)
    return Response.success(message="删除成功")


@router.post("/{key_id}/regenerate", summary="重新生成密钥")
async def regenerate_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("api-key:update")),
):
    service = ApiKeyService(db)
    _, full_key = await service.regenerate(key_id, current_user.id)
    return Response.success(data=ApiKeyRegenerateResponse(full_key=full_key).model_dump())
