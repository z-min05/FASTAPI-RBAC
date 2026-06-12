import json
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user_role import user_roles
from app.models.role_permission import role_permissions
from app.models.role_menu import role_menus
from app.models.permission import Permission
from app.models.menu import Menu
from app.models.role import Role
from app.utils.redis import get_redis

# 缓存过期时间（秒）
PERM_CACHE_TTL = 300  # 5分钟
ROLE_CACHE_TTL = 300
MENU_CACHE_TTL = 300


def _perm_cache_key(user_id: int) -> str:
    return f"rbac:user:{user_id}:permissions"


def _role_cache_key(user_id: int) -> str:
    return f"rbac:user:{user_id}:roles"


def _menu_cache_key(user_id: int) -> str:
    return f"rbac:user:{user_id}:menus"


async def invalidate_user_cache(user_id: int) -> None:
    """清除用户权限/角色/菜单缓存，修改角色或权限时调用"""
    rd = await get_redis()
    await rd.delete(_perm_cache_key(user_id), _role_cache_key(user_id), _menu_cache_key(user_id))


async def get_user_permissions(db: AsyncSession, user_id: int) -> List[str]:
    """获取用户所有权限编码列表（带 Redis 缓存）"""
    rd = await get_redis()
    cache_key = _perm_cache_key(user_id)

    # 尝试从缓存读取
    cached = await rd.get(cache_key)
    if cached:
        return json.loads(cached)

    from app.models.user import User

    user_stmt = select(User).where(User.id == user_id)
    result = await db.execute(user_stmt)
    user = result.scalar_one_or_none()
    if user and user.is_superuser:
        perm_stmt = select(Permission.code)
        result = await db.execute(perm_stmt)
        perms = [row[0] for row in result.all()]
    else:
        stmt = (
            select(Permission.code)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
            .where(user_roles.c.user_id == user_id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(Role.is_active == True)
        )
        result = await db.execute(stmt)
        perms = list(set(row[0] for row in result.all()))

    # 写入缓存
    await rd.set(cache_key, json.dumps(perms), ex=PERM_CACHE_TTL)
    return perms


async def check_permission(db: AsyncSession, user_id: int, required_permissions: List[str]) -> bool:
    """检查用户是否拥有指定权限之一"""
    user_perms = await get_user_permissions(db, user_id)
    return bool(set(user_perms).intersection(set(required_permissions)))


async def get_user_roles(db: AsyncSession, user_id: int) -> List[str]:
    """获取用户所有角色编码列表（带 Redis 缓存）"""
    rd = await get_redis()
    cache_key = _role_cache_key(user_id)

    cached = await rd.get(cache_key)
    if cached:
        return json.loads(cached)

    stmt = (
        select(Role.code)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user_id)
        .where(Role.is_active == True)
    )
    result = await db.execute(stmt)
    roles = [row[0] for row in result.all()]

    await rd.set(cache_key, json.dumps(roles), ex=ROLE_CACHE_TTL)
    return roles


async def get_user_menus(db: AsyncSession, user_id: int) -> list[dict]:
    """获取用户可见的菜单列表（带 Redis 缓存）"""
    rd = await get_redis()
    cache_key = _menu_cache_key(user_id)

    cached = await rd.get(cache_key)
    if cached:
        return json.loads(cached)

    from app.models.user import User

    user_stmt = select(User).where(User.id == user_id)
    result = await db.execute(user_stmt)
    user = result.scalar_one_or_none()

    if user and user.is_superuser:
        stmt = select(Menu).where(Menu.visible == True).order_by(Menu.sort)
        result = await db.execute(stmt)
        menus = list(result.scalars().all())
    else:
        stmt = (
            select(Menu)
            .join(role_menus, role_menus.c.menu_id == Menu.id)
            .join(user_roles, user_roles.c.role_id == role_menus.c.role_id)
            .where(user_roles.c.user_id == user_id)
            .where(Menu.visible == True)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(Role.is_active == True)
            .order_by(Menu.sort)
            .distinct()
        )
        result = await db.execute(stmt)
        menus = list(result.scalars().all())

        # 自动补全父目录：收集所有 parent_id，查询缺失的父菜单
        parent_ids = {m.parent_id for m in menus if m.parent_id is not None}
        existing_ids = {m.id for m in menus}
        missing_ids = parent_ids - existing_ids
        if missing_ids:
            parent_stmt = select(Menu).where(Menu.id.in_(missing_ids), Menu.visible == True)
            parent_result = await db.execute(parent_stmt)
            menus.extend(parent_result.scalars().all())
            menus.sort(key=lambda m: m.sort)

    menus_data = [
        {
            "id": m.id, "name": m.name, "path": m.path, "component": m.component,
            "icon": m.icon, "menu_type": m.menu_type, "parent_id": m.parent_id,
            "sort": m.sort, "visible": m.visible, "permission": m.permission,
        }
        for m in menus
    ]

    await rd.set(cache_key, json.dumps(menus_data, ensure_ascii=False), ex=MENU_CACHE_TTL)
    return menus_data
