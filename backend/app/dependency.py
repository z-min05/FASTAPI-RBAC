from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security import decode_token
from app.exceptions import UnauthorizedException, ForbiddenException
from app.models.user import User
from app.models.api_key import ApiKey
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
    """获取当前活跃用户（仅 JWT）"""
    if not current_user.is_active:
        raise UnauthorizedException("用户已被禁用")
    return current_user


async def _authenticate_api_key(token: str, db: AsyncSession) -> User:
    """通过 API Key 认证，返回权限跟随关联角色的虚拟用户"""
    from app.services.api_key_service import ApiKeyService

    api_key = await ApiKeyService.validate_key(db, token)
    if not api_key:
        raise UnauthorizedException("API 密钥无效或已过期")

    # 使用负数 ID 标记 API 密钥用户，Casbin 检查时识别为 user:api_key_{id}
    user = User(
        id=-(api_key.id),
        username=f"api_key_{api_key.id}",
        email="",
        nickname=f"API密钥({api_key.name})",
        is_active=True,
        is_superuser=False,
    )
    # 附加角色信息供后续权限校验使用
    user._api_key_role_id = api_key.role_id
    user._is_api_key = True
    return user


async def get_current_user_any(
    authorization: str = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """当前认证用户：同时支持 JWT 与 API Key

    Bearer Token 以 `sk-` 开头视为 API Key（权限跟随关联角色），
    否则视为 JWT（真实登录用户）。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("未提供认证令牌")

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise UnauthorizedException("无效的认证令牌")

    # API Key 认证
    if token.startswith("sk-"):
        return await _authenticate_api_key(token, db)

    # JWT 认证
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


async def get_current_active_user_any(
    current_user: User = Depends(get_current_user_any),
) -> User:
    """获取当前活跃用户（支持 JWT 与 API Key）"""
    if not current_user.is_active:
        raise UnauthorizedException("用户已被禁用")
    return current_user


def _require_permissions_factory(user_dependency, permissions: tuple[str, ...]):
    """权限校验依赖工厂：user_dependency 决定接受 JWT 或 JWT+API Key"""

    async def permission_checker(
        current_user: User = Depends(user_dependency),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        for perm in permissions:
            if await check_api_permission(current_user.id, perm):
                return current_user
        raise ForbiddenException(f"缺少必要权限: {', '.join(permissions)}")

    return permission_checker


def require_permissions(*permissions: str):
    """API 接口权限校验（仅 JWT 用户，系统管理模块使用）"""
    return _require_permissions_factory(get_current_active_user, permissions)


def require_permissions_any(*permissions: str):
    """API 接口权限校验（JWT 与 API Key 用户均可，业务模块使用）"""
    return _require_permissions_factory(get_current_active_user_any, permissions)


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


async def get_current_user_by_api_key(
    authorization: str = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """通过 API Key 认证（仅 API Key，不校验 JWT），返回虚拟用户对象"""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("缺少 API 密钥")

    raw_key = authorization[len("Bearer "):].strip()
    if not raw_key:
        raise UnauthorizedException("无效的 API 密钥格式")

    return await _authenticate_api_key(raw_key, db)
