from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security import decode_token
from app.exceptions import UnauthorizedException, ForbiddenException
from app.models.user import User
from app.core.rbac import check_permission
from typing import List

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    from app.repositories.user_repo import UserRepository

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedException("无效的访问令牌")
        user_id: int = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("无效的令牌载荷")
    except Exception:
        raise UnauthorizedException("无效或已过期的令牌")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException("用户不存在")
    if not user.is_active:
        raise UnauthorizedException("用户已被禁用")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise UnauthorizedException("用户已被禁用")
    return current_user


def require_permissions(*permissions: str):
    """权限校验依赖：要求当前用户拥有指定权限之一"""

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        has_perm = await check_permission(db, current_user.id, list(permissions))
        if not has_perm:
            raise ForbiddenException(f"缺少必要权限: {', '.join(permissions)}")
        return current_user

    return permission_checker


def require_roles(*roles: str):
    """角色校验依赖：要求当前用户拥有指定角色之一"""

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        from app.repositories.role_repo import RoleRepository

        repo = RoleRepository(db)
        user_roles = await repo.get_roles_by_user_id(current_user.id)
        user_role_codes = {r.code for r in user_roles}
        if not user_role_codes.intersection(set(roles)):
            raise ForbiddenException(f"缺少必要角色: {', '.join(roles)}")
        return current_user

    return role_checker
