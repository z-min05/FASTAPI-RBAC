"""
全新种子数据脚本：Casbin 三级权限体系
- API 接口权限（Permission 表，Casbin api 域）
- 菜单权限（Menu 表 menu_type=directory/menu，Casbin menu 域）
- 按钮权限（Menu 表 menu_type=button，Casbin button 域）

用法：python -m scripts.seed_data
"""
import asyncio
from sqlalchemy import select, text
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

# ==================== 测试管理模块（项目/用例）定义 ====================
TEST_PERMISSIONS = [
    {"name": "项目列表", "code": "project:list", "module": "project", "action": "list"},
    {"name": "项目详情", "code": "project:detail", "module": "project", "action": "detail"},
    {"name": "创建项目", "code": "project:create", "module": "project", "action": "create"},
    {"name": "更新项目", "code": "project:update", "module": "project", "action": "update"},
    {"name": "删除项目", "code": "project:delete", "module": "project", "action": "delete"},
    {"name": "用例列表", "code": "testcase:list", "module": "testcase", "action": "list"},
    {"name": "用例详情", "code": "testcase:detail", "module": "testcase", "action": "detail"},
    {"name": "创建用例", "code": "testcase:create", "module": "testcase", "action": "create"},
    {"name": "更新用例", "code": "testcase:update", "module": "testcase", "action": "update"},
    {"name": "删除用例", "code": "testcase:delete", "module": "testcase", "action": "delete"},
    {"name": "用例导出", "code": "testcase:export", "module": "testcase", "action": "export"},
    {"name": "用例导入", "code": "testcase:import", "module": "testcase", "action": "import"},
    {"name": "测试计划列表", "code": "plan:list", "module": "plan", "action": "list"},
    {"name": "测试计划详情", "code": "plan:detail", "module": "plan", "action": "detail"},
    {"name": "创建测试计划", "code": "plan:create", "module": "plan", "action": "create"},
    {"name": "更新测试计划", "code": "plan:update", "module": "plan", "action": "update"},
    {"name": "删除测试计划", "code": "plan:delete", "module": "plan", "action": "delete"},
    {"name": "计划用例列表", "code": "plan:case:list", "module": "plan", "action": "case:list"},
    {"name": "添加计划用例", "code": "plan:case:add", "module": "plan", "action": "case:add"},
    {"name": "记录测试结果", "code": "plan:case:result", "module": "plan", "action": "case:result"},
    {"name": "移除计划用例", "code": "plan:case:remove", "module": "plan", "action": "case:remove"},
]

TEST_MENUS = [
    {
        "name": "测试管理", "path": "/test", "icon": "AppstoreOutlined",
        "menu_type": "directory", "sort": 3, "visible": True,
        "children": [
            {
                "name": "项目管理", "path": "/test/projects", "component": "test/ProjectManage",
                "icon": "FolderOutlined", "menu_type": "menu", "sort": 1,
                "permission": "project:list", "visible": True,
                "children": [
                    {"name": "新增项目", "menu_type": "button", "permission": "project:create", "sort": 1},
                    {"name": "编辑项目", "menu_type": "button", "permission": "project:update", "sort": 2},
                    {"name": "删除项目", "menu_type": "button", "permission": "project:delete", "sort": 3},
                ],
            },
            {
                "name": "用例管理", "path": "/test/testcases", "component": "test/TestcaseManage",
                "icon": "FileTextOutlined", "menu_type": "menu", "sort": 2,
                "permission": "testcase:list", "visible": True,
                "children": [
                    {"name": "新增用例", "menu_type": "button", "permission": "testcase:create", "sort": 1},
                    {"name": "编辑用例", "menu_type": "button", "permission": "testcase:update", "sort": 2},
                    {"name": "删除用例", "menu_type": "button", "permission": "testcase:delete", "sort": 3},
                    {"name": "导入用例", "menu_type": "button", "permission": "testcase:import", "sort": 4},
                    {"name": "导出用例", "menu_type": "button", "permission": "testcase:export", "sort": 5},
                ],
            },
            {
                "name": "测试计划", "path": "/test/plans", "component": "test/TestPlanManage",
                "icon": "ScheduleOutlined", "menu_type": "menu", "sort": 3,
                "permission": "plan:list", "visible": True,
                "children": [
                    {"name": "新增计划", "menu_type": "button", "permission": "plan:create", "sort": 1},
                    {"name": "编辑计划", "menu_type": "button", "permission": "plan:update", "sort": 2},
                    {"name": "删除计划", "menu_type": "button", "permission": "plan:delete", "sort": 3},
                    {"name": "添加用例", "menu_type": "button", "permission": "plan:case:add", "sort": 4},
                    {"name": "记录结果", "menu_type": "button", "permission": "plan:case:result", "sort": 5},
                    {"name": "移除用例", "menu_type": "button", "permission": "plan:case:remove", "sort": 6},
                ],
            },
        ],
    },
]


async def _ensure_test_module(db):
    """幂等创建测试管理模块（项目/用例）的权限、菜单（含按钮）与角色授权；已存在则跳过"""
    # 1. 权限
    perm_objs = {}
    for p in TEST_PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.code == p["code"]))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(**p)
            db.add(perm)
            await db.flush()
        perm_objs[p["code"]] = perm

    # 2. 菜单（目录 -> 菜单 -> 按钮）
    module_menus = []
    for dir_def in TEST_MENUS:
        result = await db.execute(
            select(Menu).where(Menu.path == dir_def["path"], Menu.menu_type == dir_def["menu_type"])
        )
        directory = result.scalar_one_or_none()
        if not directory:
            directory = Menu(**{k: v for k, v in dir_def.items() if k != "children"})
            db.add(directory)
            await db.flush()
        module_menus.append(directory)

        for menu_def in dir_def.get("children", []):
            result = await db.execute(
                select(Menu).where(Menu.path == menu_def["path"], Menu.parent_id == directory.id)
            )
            menu = result.scalar_one_or_none()
            if not menu:
                menu = Menu(**{k: v for k, v in menu_def.items() if k != "children"}, parent_id=directory.id)
                db.add(menu)
                await db.flush()
            module_menus.append(menu)

            for btn_def in menu_def.get("children", []):
                result = await db.execute(
                    select(Menu).where(
                        Menu.permission == btn_def["permission"], Menu.menu_type == "button"
                    )
                )
                btn = result.scalar_one_or_none()
                if not btn:
                    btn = Menu(
                        name=btn_def["name"], menu_type="button",
                        permission=btn_def["permission"], parent_id=menu.id, sort=btn_def["sort"],
                    )
                    db.add(btn)
                    await db.flush()
                module_menus.append(btn)

    # 3. 角色授权（admin 全部；user 只读 list 权限 + 非按钮菜单）
    admin_role = (await db.execute(select(Role).where(Role.code == "admin"))).scalar_one_or_none()
    user_role = (await db.execute(select(Role).where(Role.code == "user"))).scalar_one_or_none()

    for code, perm in perm_objs.items():
        if admin_role:
            r = await db.execute(
                select(role_permissions).where(
                    role_permissions.c.role_id == admin_role.id,
                    role_permissions.c.permission_id == perm.id,
                )
            )
            if not r.first():
                await db.execute(
                    role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
                )
        if user_role and code.endswith(":list"):
            r = await db.execute(
                select(role_permissions).where(
                    role_permissions.c.role_id == user_role.id,
                    role_permissions.c.permission_id == perm.id,
                )
            )
            if not r.first():
                await db.execute(
                    role_permissions.insert().values(role_id=user_role.id, permission_id=perm.id)
                )

    for m in module_menus:
        if admin_role:
            r = await db.execute(
                select(role_menus).where(role_menus.c.role_id == admin_role.id, role_menus.c.menu_id == m.id)
            )
            if not r.first():
                await db.execute(role_menus.insert().values(role_id=admin_role.id, menu_id=m.id))
        if user_role and m.menu_type != "button":
            r = await db.execute(
                select(role_menus).where(role_menus.c.role_id == user_role.id, role_menus.c.menu_id == m.id)
            )
            if not r.first():
                await db.execute(role_menus.insert().values(role_id=user_role.id, menu_id=m.id))


# ==================== Agent（AI 助手）模块定义 ====================
# 说明：Agent 对话 / 我的 Agent / Token 统计 改为“登录即可访问”，入口在右上角
# 用户下拉菜单，不再由 RBAC 菜单/权限管理；LLM 配置为平台级配置，保留在左侧
# 菜单中，增删改查均按 RBAC 细粒度授权（agent:llm:list/detail/create/update/delete）。
AGENT_PERMISSIONS = [
    {"name": "LLM 配置列表", "code": "agent:llm:list", "module": "agent", "action": "list"},
    {"name": "LLM 配置详情", "code": "agent:llm:detail", "module": "agent", "action": "detail"},
    {"name": "新增 LLM 配置", "code": "agent:llm:create", "module": "agent", "action": "create"},
    {"name": "编辑 LLM 配置", "code": "agent:llm:update", "module": "agent", "action": "update"},
    {"name": "删除 LLM 配置", "code": "agent:llm:delete", "module": "agent", "action": "delete"},
]

AGENT_MENUS = [
    {
        "name": "AI 助手", "path": "/agent", "icon": "RobotOutlined",
        "menu_type": "directory", "sort": 4, "visible": True,
        "children": [
            {
                "name": "LLM 配置", "path": "/agent/llms", "component": "agent/LlmManage",
                "icon": "ApiOutlined", "menu_type": "menu", "sort": 1,
                "permission": "agent:llm:list", "visible": True,
                "children": [
                    {"name": "新增 LLM", "menu_type": "button", "permission": "agent:llm:create", "sort": 1},
                    {"name": "编辑 LLM", "menu_type": "button", "permission": "agent:llm:update", "sort": 2},
                    {"name": "删除 LLM", "menu_type": "button", "permission": "agent:llm:delete", "sort": 3},
                ],
            },
        ],
    },
]

# 旧版本遗留、已废弃的权限/菜单（升级时幂等清理）
# 注意：agent:llm 为上一版“单一管理权限”，本次升级替换为 agent:llm:* 细粒度
AGENT_OBSOLETE_PERMISSION_CODES = {"agent:chat", "agent:delete", "agent:stats", "agent:llm"}
AGENT_OBSOLETE_MENU_PATHS = {"/agent/chat", "/agent/manage"}


async def _ensure_agent_module(db):
    """幂等创建 AI 助手模块数据，并清理旧版本废弃的权限/菜单/授权。

    - 权限：LLM 配置按 agent:llm:list/detail/create/update/delete 细粒度授权
    - 菜单：目录 /agent 下仅保留 LLM 配置（含 新增/编辑/删除 按钮）
    - 角色：admin 全部；user 默认仅 list/detail（只读）与非按钮菜单，
      其余动作通过 RBAC 分配（与测试管理模块一致）
    """
    # 1. 权限：新增 agent:llm:*；删除废弃权限（agent:chat/agent:delete/agent:stats/agent:llm）
    perm_objs = {}
    for p in AGENT_PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.code == p["code"]))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(**p)
            db.add(perm)
            await db.flush()
        perm_objs[p["code"]] = perm

    if AGENT_OBSOLETE_PERMISSION_CODES:
        obsolete_perms = (
            await db.execute(
                select(Permission).where(Permission.code.in_(AGENT_OBSOLETE_PERMISSION_CODES))
            )
        ).scalars().all()
        for p in obsolete_perms:
            await db.delete(p)

    # 2. 菜单（目录 /agent -> LLM 配置 menu -> 新增/编辑/删除 按钮）
    module_menus = []
    for dir_def in AGENT_MENUS:
        result = await db.execute(
            select(Menu).where(Menu.path == dir_def["path"], Menu.menu_type == dir_def["menu_type"])
        )
        directory = result.scalar_one_or_none()
        if not directory:
            directory = Menu(**{k: v for k, v in dir_def.items() if k != "children"})
            db.add(directory)
            await db.flush()
        module_menus.append(directory)

        for menu_def in dir_def.get("children", []):
            result = await db.execute(
                select(Menu).where(Menu.path == menu_def["path"], Menu.parent_id == directory.id)
            )
            menu = result.scalar_one_or_none()
            if not menu:
                menu = Menu(**{k: v for k, v in menu_def.items() if k != "children"}, parent_id=directory.id)
                db.add(menu)
                await db.flush()
            elif menu.permission != menu_def["permission"]:
                # 升级场景：旧行 permission 是 agent:chat/agent:llm，统一改为 agent:llm:list
                menu.permission = menu_def["permission"]
            module_menus.append(menu)

            for btn_def in menu_def.get("children", []):
                result = await db.execute(
                    select(Menu).where(
                        Menu.permission == btn_def["permission"], Menu.menu_type == "button"
                    )
                )
                btn = result.scalar_one_or_none()
                if not btn:
                    btn = Menu(
                        name=btn_def["name"], menu_type="button",
                        permission=btn_def["permission"], parent_id=menu.id, sort=btn_def["sort"],
                    )
                    db.add(btn)
                    await db.flush()
                module_menus.append(btn)

    # 3. 清理旧菜单：Agent 对话(/agent/chat)、我的 Agent(/agent/manage)、旧按钮
    if AGENT_OBSOLETE_MENU_PATHS:
        old_menus = (
            await db.execute(
                select(Menu).where(
                    Menu.menu_type == "menu", Menu.path.in_(AGENT_OBSOLETE_MENU_PATHS)
                )
            )
        ).scalars().all()
        for m in old_menus:
            await db.delete(m)
    if AGENT_OBSOLETE_PERMISSION_CODES:
        old_buttons = (
            await db.execute(
                select(Menu).where(
                    Menu.menu_type == "button",
                    Menu.permission.in_(AGENT_OBSOLETE_PERMISSION_CODES),
                )
            )
        ).scalars().all()
        for b in old_buttons:
            await db.delete(b)

    # 4. 角色授权（admin 全部；user 仅 :list/:detail 只读权限 + 非按钮菜单）
    admin_role = (await db.execute(select(Role).where(Role.code == "admin"))).scalar_one_or_none()
    user_role = (await db.execute(select(Role).where(Role.code == "user"))).scalar_one_or_none()

    for code, perm in perm_objs.items():
        if admin_role:
            r = await db.execute(
                select(role_permissions).where(
                    role_permissions.c.role_id == admin_role.id,
                    role_permissions.c.permission_id == perm.id,
                )
            )
            if not r.first():
                await db.execute(
                    role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
                )
        if user_role and code.endswith(":list"):
            r = await db.execute(
                select(role_permissions).where(
                    role_permissions.c.role_id == user_role.id,
                    role_permissions.c.permission_id == perm.id,
                )
            )
            if not r.first():
                await db.execute(
                    role_permissions.insert().values(role_id=user_role.id, permission_id=perm.id)
                )

    for m in module_menus:
        if admin_role:
            r = await db.execute(
                select(role_menus).where(role_menus.c.role_id == admin_role.id, role_menus.c.menu_id == m.id)
            )
            if not r.first():
                await db.execute(role_menus.insert().values(role_id=admin_role.id, menu_id=m.id))
        if user_role and m.menu_type != "button":
            r = await db.execute(
                select(role_menus).where(role_menus.c.role_id == user_role.id, role_menus.c.menu_id == m.id)
            )
            if not r.first():
                await db.execute(role_menus.insert().values(role_id=user_role.id, menu_id=m.id))


async def _sync_casbin(db):
    """同步 Casbin 策略到数据库"""
    from app.core.casbin_service import get_enforcer, sync_policies
    await get_enforcer()
    await sync_policies(db)
    print("Casbin 策略同步完成")


async def seed():
    # 1. 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建完成")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            # 已有数据：增量补充新增模块的权限/菜单/角色授权（幂等）
            print("检测到已有数据，增量补充测试管理/AI 助手模块权限/菜单")
            await _ensure_test_module(db)
            await _ensure_agent_module(db)
            await db.commit()
            await _sync_casbin(db)
            print("增量补充完成")
            return

        # ==================== 权限（API 接口权限） ====================
        permissions_data = [
            # 用户模块
            {"name": "用户列表", "code": "user:list", "module": "user", "action": "list"},
            {"name": "用户详情", "code": "user:detail", "module": "user", "action": "detail"},
            {"name": "创建用户", "code": "user:create", "module": "user", "action": "create"},
            {"name": "更新用户", "code": "user:update", "module": "user", "action": "update"},
            {"name": "删除用户", "code": "user:delete", "module": "user", "action": "delete"},
            # 角色模块
            {"name": "角色列表", "code": "role:list", "module": "role", "action": "list"},
            {"name": "角色详情", "code": "role:detail", "module": "role", "action": "detail"},
            {"name": "创建角色", "code": "role:create", "module": "role", "action": "create"},
            {"name": "更新角色", "code": "role:update", "module": "role", "action": "update"},
            {"name": "删除角色", "code": "role:delete", "module": "role", "action": "delete"},
            # 权限模块
            {"name": "权限列表", "code": "permission:list", "module": "permission", "action": "list"},
            {"name": "权限详情", "code": "permission:detail", "module": "permission", "action": "detail"},
            {"name": "创建权限", "code": "permission:create", "module": "permission", "action": "create"},
            {"name": "更新权限", "code": "permission:update", "module": "permission", "action": "update"},
            {"name": "删除权限", "code": "permission:delete", "module": "permission", "action": "delete"},
            # 菜单模块
            {"name": "菜单列表", "code": "menu:list", "module": "menu", "action": "list"},
            {"name": "菜单详情", "code": "menu:detail", "module": "menu", "action": "detail"},
            {"name": "创建菜单", "code": "menu:create", "module": "menu", "action": "create"},
            {"name": "更新菜单", "code": "menu:update", "module": "menu", "action": "update"},
            {"name": "删除菜单", "code": "menu:delete", "module": "menu", "action": "delete"},
            # 部门模块
            {"name": "部门列表", "code": "department:list", "module": "department", "action": "list"},
            {"name": "部门详情", "code": "department:detail", "module": "department", "action": "detail"},
            {"name": "创建部门", "code": "department:create", "module": "department", "action": "create"},
            {"name": "更新部门", "code": "department:update", "module": "department", "action": "update"},
            {"name": "删除部门", "code": "department:delete", "module": "department", "action": "delete"},
            # 日志模块
            {"name": "日志列表", "code": "log:list", "module": "log", "action": "list"},
        ]
        perms = []
        for p in permissions_data:
            perm = Permission(**p)
            db.add(perm)
            perms.append(perm)
        await db.flush()
        print(f"创建 {len(perms)} 个 API 权限")

        # ==================== 菜单（含按钮权限） ====================
        # 一级目录：仪表盘
        dashboard_menu = Menu(
            name="仪表盘", path="/dashboard", icon="DashboardOutlined",
            menu_type="menu", sort=0, visible=True
        )
        db.add(dashboard_menu)
        await db.flush()

        # 一级目录：系统管理
        system_menu = Menu(
            name="系统管理", path="/system", icon="SettingOutlined",
            menu_type="directory", sort=1, visible=True
        )
        db.add(system_menu)
        await db.flush()

        # 二级菜单 + 按钮权限（挂在系统管理下）
        user_menu = Menu(
            name="用户管理", path="/system/users", component="system/users/index",
            icon="UserOutlined", menu_type="menu", parent_id=system_menu.id,
            sort=1, permission="user:list"
        )
        db.add(user_menu)
        await db.flush()

        # 用户管理下的按钮
        user_buttons = [
            {"name": "新增用户", "permission": "user:create", "sort": 1},
            {"name": "编辑用户", "permission": "user:update", "sort": 2},
            {"name": "删除用户", "permission": "user:delete", "sort": 3},
        ]
        for b in user_buttons:
            db.add(Menu(
                name=b["name"], menu_type="button",
                parent_id=user_menu.id, permission=b["permission"], sort=b["sort"]
            ))
        await db.flush()

        role_menu = Menu(
            name="角色管理", path="/system/roles", component="system/roles/index",
            icon="TeamOutlined", menu_type="menu", parent_id=system_menu.id,
            sort=2, permission="role:list"
        )
        db.add(role_menu)
        await db.flush()

        role_buttons = [
            {"name": "新增角色", "permission": "role:create", "sort": 1},
            {"name": "编辑角色", "permission": "role:update", "sort": 2},
            {"name": "删除角色", "permission": "role:delete", "sort": 3},
        ]
        for b in role_buttons:
            db.add(Menu(
                name=b["name"], menu_type="button",
                parent_id=role_menu.id, permission=b["permission"], sort=b["sort"]
            ))
        await db.flush()

        perm_menu = Menu(
            name="权限管理", path="/system/permissions", component="system/permissions/index",
            icon="SafetyOutlined", menu_type="menu", parent_id=system_menu.id,
            sort=3, permission="permission:list"
        )
        db.add(perm_menu)
        await db.flush()

        perm_buttons = [
            {"name": "新增权限", "permission": "permission:create", "sort": 1},
            {"name": "编辑权限", "permission": "permission:update", "sort": 2},
            {"name": "删除权限", "permission": "permission:delete", "sort": 3},
        ]
        for b in perm_buttons:
            db.add(Menu(
                name=b["name"], menu_type="button",
                parent_id=perm_menu.id, permission=b["permission"], sort=b["sort"]
            ))
        await db.flush()

        menu_menu = Menu(
            name="菜单管理", path="/system/menus", component="system/menus/index",
            icon="MenuOutlined", menu_type="menu", parent_id=system_menu.id,
            sort=4, permission="menu:list"
        )
        db.add(menu_menu)
        await db.flush()

        menu_buttons = [
            {"name": "新增菜单", "permission": "menu:create", "sort": 1},
            {"name": "编辑菜单", "permission": "menu:update", "sort": 2},
            {"name": "删除菜单", "permission": "menu:delete", "sort": 3},
        ]
        for b in menu_buttons:
            db.add(Menu(
                name=b["name"], menu_type="button",
                parent_id=menu_menu.id, permission=b["permission"], sort=b["sort"]
            ))
        await db.flush()

        dept_menu = Menu(
            name="部门管理", path="/system/departments", component="system/departments/index",
            icon="ApartmentOutlined", menu_type="menu", parent_id=system_menu.id,
            sort=5, permission="department:list"
        )
        db.add(dept_menu)
        await db.flush()

        dept_buttons = [
            {"name": "新增部门", "permission": "department:create", "sort": 1},
            {"name": "编辑部门", "permission": "department:update", "sort": 2},
            {"name": "删除部门", "permission": "department:delete", "sort": 3},
        ]
        for b in dept_buttons:
            db.add(Menu(
                name=b["name"], menu_type="button",
                parent_id=dept_menu.id, permission=b["permission"], sort=b["sort"]
            ))
        await db.flush()

        log_menu = Menu(
            name="操作日志", path="/system/logs", component="system/logs/index",
            icon="FileTextOutlined", menu_type="menu", parent_id=system_menu.id,
            sort=6, permission="log:list"
        )
        db.add(log_menu)
        await db.flush()

        # 获取所有菜单 ID
        all_menus_result = await db.execute(select(Menu))
        all_menus = list(all_menus_result.scalars().all())
        all_menu_ids = [m.id for m in all_menus]
        print(f"创建 {len(all_menus)} 个菜单（含按钮）")

        # ==================== 角色 ====================
        admin_role = Role(name="超级管理员", code="admin", description="拥有所有权限", sort=0)
        db.add(admin_role)
        await db.flush()

        user_role = Role(name="普通用户", code="user", description="基础查看权限", sort=1)
        db.add(user_role)
        await db.flush()

        # ==================== 关联：角色 <-> 权限 ====================
        # 管理员拥有所有权限
        for perm in perms:
            await db.execute(
                role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
            )

        # 普通用户只有 list 权限
        list_perms = [p for p in perms if p.action == "list"]
        for perm in list_perms:
            await db.execute(
                role_permissions.insert().values(role_id=user_role.id, permission_id=perm.id)
            )

        # ==================== 关联：角色 <-> 菜单 ====================
        # 管理员拥有所有菜单
        for menu_id in all_menu_ids:
            await db.execute(
                role_menus.insert().values(role_id=admin_role.id, menu_id=menu_id)
            )

        # 普通用户只有菜单（不含按钮）
        non_button_menus = [m for m in all_menus if m.menu_type != "button"]
        for m in non_button_menus:
            await db.execute(
                role_menus.insert().values(role_id=user_role.id, menu_id=m.id)
            )

        # 测试管理模块（项目/用例）权限 + 菜单 + 按钮 + 角色授权
        await _ensure_test_module(db)

        # Agent（AI 助手）模块权限 + 菜单 + 按钮 + 角色授权
        await _ensure_agent_module(db)

        # ==================== 用户 ====================
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

        test_user = User(
            username="user",
            email="user@example.com",
            hashed_password=get_password_hash("user123456"),
            nickname="普通用户",
            is_active=True,
            is_superuser=False,
        )
        db.add(test_user)
        await db.flush()

        await db.execute(
            user_roles.insert().values(user_id=admin_user.id, role_id=admin_role.id)
        )
        await db.execute(
            user_roles.insert().values(user_id=test_user.id, role_id=user_role.id)
        )

        # ==================== 部门 ====================
        root_dept = Department(name="总公司", code="HQ", sort=0, leader="admin")
        db.add(root_dept)

        await db.commit()
        print("种子数据初始化完成")
        print(f"  - {len(perms)} 个 API 权限")
        print(f"  - {len(all_menus)} 个菜单（含按钮）")
        print(f"  - 2 个角色（admin, user）")
        print(f"  - 2 个用户（admin/admin123456, user/user123456）")

        await _sync_casbin(db)


async def reset_and_seed():
    """清空数据库并重新初始化（危险操作！）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("已清空所有表")
    await seed()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_and_seed())
    else:
        asyncio.run(seed())
