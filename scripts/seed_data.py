import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal, engine
from app.models.base import Base
from app.security import get_password_hash
from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.menu import Menu
from app.models.department import Department
from app.models.user_role import user_roles
from app.models.role_permission import role_permissions
from app.models.role_menu import role_menus
from sqlalchemy import select


async def seed():
    # 先创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建完成")

    async with AsyncSessionLocal() as db:
        # 检查是否已有数据
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("种子数据已存在，跳过初始化")
            return

        # 创建默认权限
        permissions_data = [
            {"name": "用户列表", "code": "user:list", "module": "user", "action": "list"},
            {"name": "用户详情", "code": "user:detail", "module": "user", "action": "detail"},
            {"name": "创建用户", "code": "user:create", "module": "user", "action": "create"},
            {"name": "更新用户", "code": "user:update", "module": "user", "action": "update"},
            {"name": "删除用户", "code": "user:delete", "module": "user", "action": "delete"},
            {"name": "角色列表", "code": "role:list", "module": "role", "action": "list"},
            {"name": "角色详情", "code": "role:detail", "module": "role", "action": "detail"},
            {"name": "创建角色", "code": "role:create", "module": "role", "action": "create"},
            {"name": "更新角色", "code": "role:update", "module": "role", "action": "update"},
            {"name": "删除角色", "code": "role:delete", "module": "role", "action": "delete"},
            {"name": "权限列表", "code": "permission:list", "module": "permission", "action": "list"},
            {"name": "菜单列表", "code": "menu:list", "module": "menu", "action": "list"},
            {"name": "部门列表", "code": "department:list", "module": "department", "action": "list"},
            {"name": "日志列表", "code": "log:list", "module": "log", "action": "list"},
        ]
        perms = []
        for p in permissions_data:
            perm = Permission(**p)
            db.add(perm)
            perms.append(perm)
        await db.flush()

        # 创建超级管理员角色
        admin_role = Role(name="超级管理员", code="admin", description="拥有所有权限", sort=0)
        db.add(admin_role)
        await db.flush()

        # 关联管理员角色与所有权限
        for perm in perms:
            await db.execute(
                role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
            )

        # 创建普通用户角色
        user_role = Role(name="普通用户", code="user", description="基础权限", sort=1)
        db.add(user_role)
        await db.flush()

        # 创建超级管理员用户
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123456"),
            nickname="超级管理员",
            is_active=True,
            is_superuser=True,
        )
        db.add(admin_user)
        await db.flush()

        # 关联管理员用户与管理员角色
        await db.execute(
            user_roles.insert().values(user_id=admin_user.id, role_id=admin_role.id)
        )

        # 创建默认部门
        root_dept = Department(name="总公司", code="HQ", sort=0, leader="admin")
        db.add(root_dept)

        # 创建默认菜单
        menus_data = [
            {"name": "系统管理", "path": "/system", "menu_type": "directory", "sort": 1},
            {"name": "用户管理", "path": "/system/users", "component": "system/users/index", "menu_type": "menu", "parent_id": None, "sort": 1, "permission": "user:list"},
            {"name": "角色管理", "path": "/system/roles", "component": "system/roles/index", "menu_type": "menu", "parent_id": None, "sort": 2, "permission": "role:list"},
            {"name": "权限管理", "path": "/system/permissions", "component": "system/permissions/index", "menu_type": "menu", "parent_id": None, "sort": 3, "permission": "permission:list"},
        ]
        for m in menus_data:
            menu = Menu(**m)
            db.add(menu)

        await db.commit()
        print("种子数据初始化完成")


if __name__ == "__main__":
    asyncio.run(seed())
