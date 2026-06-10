from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user_role import user_roles
from app.models.role_permission import role_permissions
from app.models.permission import Permission
from app.models.role import Role


async def get_user_permissions(db: AsyncSession, user_id: int) -> List[str]:
    """获取用户所有权限编码列表"""
    # 超级用户拥有所有权限
    from app.models.user import User

    user_stmt = select(User).where(User.id == user_id)
    result = await db.execute(user_stmt)
    user = result.scalar_one_or_none()
    if user and user.is_superuser:
        perm_stmt = select(Permission.code)
        result = await db.execute(perm_stmt)
        return [row[0] for row in result.all()]

    # 通过用户角色获取权限
    stmt = (
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
        .where(user_roles.c.user_id == user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.is_active == True)
    )
    result = await db.execute(stmt)
    return list(set(row[0] for row in result.all()))


async def check_permission(db: AsyncSession, user_id: int, required_permissions: List[str]) -> bool:
    """检查用户是否拥有指定权限之一"""
    user_perms = await get_user_permissions(db, user_id)
    return bool(set(user_perms).intersection(set(required_permissions)))


async def get_user_roles(db: AsyncSession, user_id: int) -> List[str]:
    """获取用户所有角色编码列表"""
    stmt = (
        select(Role.code)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user_id)
        .where(Role.is_active == True)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]
