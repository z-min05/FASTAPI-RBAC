from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.response import Response

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="获取用户列表")
async def get_users(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:list")),
):
    service = UserService(db)
    result = await service.get_users(params)
    return Response.success(data=result.model_dump())


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:detail")),
):
    service = UserService(db)
    user = await service.get_user(user_id)
    return Response.success(data=UserResponse.model_validate(user).model_dump())


@router.post("", summary="创建用户")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:create")),
):
    service = UserService(db)
    user = await service.create_user(data)
    return Response.success(data=UserResponse.model_validate(user).model_dump())


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:update")),
):
    service = UserService(db)
    user = await service.update_user(user_id, data)
    return Response.success(data=UserResponse.model_validate(user).model_dump())


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:delete")),
):
    service = UserService(db)
    await service.delete_user(user_id)
    return Response.success(message="删除成功")
