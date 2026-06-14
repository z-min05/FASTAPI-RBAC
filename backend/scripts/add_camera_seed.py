"""增量添加摄像头模块的菜单和权限数据（适用于已有数据库）"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.permission import Permission
from app.models.menu import Menu
from app.models.role import Role
from app.models.role_permission import role_permissions
from app.models.role_menu import role_menus


async def add_camera_seed():
    async with AsyncSessionLocal() as db:
        # 添加摄像头权限（跳过已存在的）
        permissions_data = [
            {"name": "摄像头列表", "code": "camera:list", "module": "camera", "action": "list"},
            {"name": "摄像头详情", "code": "camera:detail", "module": "camera", "action": "detail"},
            {"name": "创建摄像头", "code": "camera:create", "module": "camera", "action": "create"},
            {"name": "更新摄像头", "code": "camera:update", "module": "camera", "action": "update"},
            {"name": "删除摄像头", "code": "camera:delete", "module": "camera", "action": "delete"},
            {"name": "摄像头连接", "code": "camera:connect", "module": "camera", "action": "connect"},
            {"name": "云台控制", "code": "camera:ptz", "module": "camera", "action": "ptz"},
            {"name": "摄像头抓图", "code": "camera:snapshot", "module": "camera", "action": "snapshot"},
            {"name": "视频流管理", "code": "camera:stream", "module": "camera", "action": "stream"},
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

        # 创建"设备管理"一级目录菜单
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

        # 创建"摄像头管理"二级菜单（挂在设备管理下）
        result = await db.execute(select(Menu).where(Menu.path == "/device/cameras"))
        camera_menu = result.scalar_one_or_none()

        if not camera_menu:
            camera_menu = Menu(
                name="摄像头管理",
                path="/device/cameras",
                component="device/cameras/index",
                icon="VideoCameraOutlined",
                menu_type="menu",
                parent_id=device_menu.id,
                sort=1,
                permission="camera:list"
            )
            db.add(camera_menu)
            await db.flush()
            print("  添加二级菜单: 摄像头管理")

        # 将新权限和菜单关联到超级管理员角色
        result = await db.execute(select(Role).where(Role.code == "admin"))
        admin_role = result.scalar_one_or_none()

        if admin_role:
            # 关联权限
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

            # 关联设备管理目录菜单
            for menu in [device_menu, camera_menu]:
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
        print("摄像头模块种子数据添加完成")


if __name__ == "__main__":
    asyncio.run(add_camera_seed())
