from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security import decode_token
from app.exceptions import UnauthorizedException, ForbiddenException
from app.models.user import User
from app.core.casbin_service import (
    check_api_permission,
    check_menu_permission,
    check_button_permission,
)
from app.utils.logger import logger
from jose import JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    from app.repositories.user_repo import UserRepository

    try:
        payload = decode_token(token)
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise UnauthorizedException("无效或已过期的令牌")

    if payload.get("type") != "access":
        raise UnauthorizedException("无效的访问令牌")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedException("无效的令牌载荷")

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
    """API 接口权限校验（兼容旧代码，等同于 require_api_permission）"""

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        for perm in permissions:
            if await check_api_permission(current_user.id, perm):
                return current_user
        raise ForbiddenException(f"缺少必要权限: {', '.join(permissions)}")

    return permission_checker


def require_api_permission(permission_code: str):
    """API 接口权限校验：检查用户是否拥有指定的 API 权限"""

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        if await check_api_permission(current_user.id, permission_code):
            return current_user
        raise ForbiddenException(f"缺少API权限: {permission_code}")

    return permission_checker


def require_menu_permission(menu_path: str):
    """菜单权限校验：检查用户是否拥有指定菜单的访问权限"""

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        if await check_menu_permission(current_user.id, menu_path):
            return current_user
        raise ForbiddenException(f"缺少菜单权限: {menu_path}")

    return permission_checker


def require_button_permission(button_code: str):
    """按钮权限校验：检查用户是否拥有指定按钮的操作权限"""

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        if await check_button_permission(current_user.id, button_code):
            return current_user
        raise ForbiddenException(f"缺少按钮权限: {button_code}")

    return permission_checker


def require_roles(*roles: str):
    """角色校验依赖：要求当前用户拥有指定角色之一"""

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        from app.repositories.role_repo import RoleRepository

        repo = RoleRepository(db)
        user_roles = await repo.get_roles_by_user_id(current_user.id)
        user_role_codes = {r.code for r in user_roles}
        if not user_role_codes.intersection(set(roles)):
            raise ForbiddenException(f"缺少必要角色: {', '.join(roles)}")
        return current_user

    return role_checker
