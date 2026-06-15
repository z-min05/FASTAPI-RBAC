"""增量添加YOLO识别模块的菜单和权限数据（适用于已有数据库）"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.permission import Permission
from app.models.menu import Menu
from app.models.role import Role
from app.models.role_permission import role_permissions
from app.models.role_menu import role_menus


async def add_yolo_seed():
    async with AsyncSessionLocal() as db:
        # 添加YOLO模块权限
        permissions_data = [
            {"name": "YOLO模型列表", "code": "yolo:model:list", "module": "yolo", "action": "list"},
            {"name": "YOLO模型详情", "code": "yolo:model:detail", "module": "yolo", "action": "detail"},
            {"name": "创建YOLO模型", "code": "yolo:model:create", "module": "yolo", "action": "create"},
            {"name": "更新YOLO模型", "code": "yolo:model:update", "module": "yolo", "action": "update"},
            {"name": "删除YOLO模型", "code": "yolo:model:delete", "module": "yolo", "action": "delete"},
            {"name": "识别任务列表", "code": "yolo:task:list", "module": "yolo", "action": "list"},
            {"name": "识别任务详情", "code": "yolo:task:detail", "module": "yolo", "action": "detail"},
            {"name": "创建识别任务", "code": "yolo:task:create", "module": "yolo", "action": "create"},
            {"name": "更新识别任务", "code": "yolo:task:update", "module": "yolo", "action": "update"},
            {"name": "删除识别任务", "code": "yolo:task:delete", "module": "yolo", "action": "delete"},
            {"name": "启停识别任务", "code": "yolo:task:toggle", "module": "yolo", "action": "toggle"},
            {"name": "手动执行识别", "code": "yolo:task:run", "module": "yolo", "action": "run"},
            {"name": "识别结果列表", "code": "yolo:result:list", "module": "yolo", "action": "list"},
            {"name": "识别结果详情", "code": "yolo:result:detail", "module": "yolo", "action": "detail"},
        ]

        new_perms = []
        for p in permissions_data:
            result = await db.execute(select(Permission).where(Permission.code == p["code"]))
            existing = result.scalar_one_or_none()
            if not existing:
                perm = Permission(**p)
                db.add(perm)
                new_perms.append(perm)
                print(f"  添加权限: {p['code']}")
            else:
                new_perms.append(existing)
        await db.flush()

        # 查找"设备管理"一级目录菜单
        result = await db.execute(select(Menu).where(Menu.path == "/device"))
        device_menu = result.scalar_one_or_none()
        if not device_menu:
            device_menu = Menu(
                name="设备管理",
                path="/device",
                icon="DesktopOutlined",
                menu_type="directory",
                sort=2,
                visible=True
            )
            db.add(device_menu)
            await db.flush()
            print("  添加一级目录菜单: 设备管理")

        # 创建"YOLO识别"二级菜单（挂在设备管理下）
        result = await db.execute(select(Menu).where(Menu.path == "/device/yolo"))
        yolo_menu = result.scalar_one_or_none()
        if not yolo_menu:
            yolo_menu = Menu(
                name="YOLO识别",
                path="/device/yolo",
                component="device/yolo/index",
                icon="ScanOutlined",
                menu_type="menu",
                parent_id=device_menu.id,
                sort=2,
                permission="yolo:model:list"
            )
            db.add(yolo_menu)
            await db.flush()
            print("  添加二级菜单: YOLO识别")

        # 创建"识别任务"二级菜单（挂在设备管理下）
        result = await db.execute(select(Menu).where(Menu.path == "/device/yolo/tasks"))
        task_menu = result.scalar_one_or_none()
        if not task_menu:
            task_menu = Menu(
                name="识别任务",
                path="/device/yolo/tasks",
                component="device/yolo/tasks",
                icon="AimOutlined",
                menu_type="menu",
                parent_id=device_menu.id,
                sort=3,
                permission="yolo:task:list"
            )
            db.add(task_menu)
            await db.flush()
            print("  添加二级菜单: 识别任务")

        # 将新权限和菜单关联到超级管理员角色
        result = await db.execute(select(Role).where(Role.code == "admin"))
        admin_role = result.scalar_one_or_none()

        if admin_role:
            for perm in new_perms:
                result = await db.execute(
                    select(role_permissions).where(
                        role_permissions.c.role_id == admin_role.id,
                        role_permissions.c.permission_id == perm.id
                    )
                )
                if not result.first():
                    await db.execute(
                        role_permissions.insert().values(
                            role_id=admin_role.id, permission_id=perm.id
                        )
                    )
                    print(f"  关联权限到admin角色: {perm.code}")

            for menu in [device_menu, yolo_menu, task_menu]:
                if menu:
                    result = await db.execute(
                        select(role_menus).where(
                            role_menus.c.role_id == admin_role.id,
                            role_menus.c.menu_id == menu.id
                        )
                    )
                    if not result.first():
                        await db.execute(
                            role_menus.insert().values(
                                role_id=admin_role.id, menu_id=menu.id
                            )
                        )
                        print(f"  关联菜单到admin角色: {menu.name}")

        await db.commit()
        print("YOLO识别模块种子数据添加完成")


if __name__ == "__main__":
    asyncio.run(add_yolo_seed())
