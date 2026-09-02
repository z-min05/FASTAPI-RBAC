from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserWithRolesResponse
from app.services.user_service import UserService
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.response import Response
from app.security import verify_password, get_password_hash
from app.exceptions import BadRequestException

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="获取用户列表")
async def get_users(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:list")),
):
    service = UserService(db)
    result = await service.get_users(params)
    raw = result.model_dump()
    # 用 UserWithRolesResponse 序列化以包含 roles 关系
    raw["items"] = [UserWithRolesResponse.model_validate(u).model_dump() for u in result.items]
    return Response.success(data=raw)


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("user:detail")),
):
    service = UserService(db)
    user = await service.get_user(user_id)
    return Response.success(data=UserWithRolesResponse.model_validate(user).model_dump())


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
    current_user: User = Depends(get_current_active_user),
):
    # 普通用户只能修改自己，且不能修改角色等敏感字段
    if current_user.id == user_id and not current_user.is_superuser:
        data.role_ids = None
        data.is_active = None
    elif not current_user.is_superuser:
        # 非本人且非超管，需要 user:update 权限
        from app.dependency import require_permissions
        checker = require_permissions("user:update")
        await checker(current_user)
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


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


@router.put("/{user_id}/password", summary="修改密码")
async def change_password(
    user_id: int,
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """用户修改自己的密码"""
    if current_user.id != user_id:
        raise BadRequestException("只能修改自己的密码")
    if not verify_password(data.old_password, current_user.hashed_password):
        raise BadRequestException("当前密码错误")
    current_user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    return Response.success(message="密码修改成功")
