"""
Casbin 权限服务：基于 RBAC + 域模型实现 API/菜单/按钮三种权限控制

域（dom）说明：
- api:    API 接口权限，obj=权限编码，act=access
- menu:   菜单权限，obj=菜单路径，act=access
- button: 按钮权限，obj=权限编码，act=click

设计决策：
- Permission 表：只管 API 接口权限
- Menu 表 menu_type='button'：只管前端按钮权限
- 双缓冲：构建新 Enforcer 后原子替换，避免策略真空
- PostgreSQL 适配器：策略持久化，支持多 Worker
- Redis 版本号：多 Worker 间同步策略变更
"""
import asyncio
import os
import threading
from datetime import datetime
from typing import List

from casbin import Enforcer
from sqlalchemy import select, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_role import user_roles
from app.models.role_permission import role_permissions
from app.models.role_menu import role_menus
from app.models.permission import Permission
from app.models.menu import Menu
from app.models.role import Role
from app.models.api_key import ApiKey
from app.utils.logger import logger

# 权限域常量
DOMAIN_API = "api"
DOMAIN_MENU = "menu"
DOMAIN_BUTTON = "button"

# Redis 版本号 key
POLICY_VERSION_KEY = "casbin:policy_version"

# 超管用户 ID 缓存（LRU）
_superuser_cache: dict[int, bool] = {}
_superuser_cache_lock = threading.Lock()

# Enforcer 单例 + 双重锁
_enforcer: Enforcer | None = None
_enforcer_lock = threading.Lock()
_async_init_lock = asyncio.Lock()

# 当前策略版本号
_local_version: int = 0


def _get_model_path() -> str:
    return os.path.join(os.path.dirname(__file__), "casbin_model.conf")


def _create_sync_engine():
    """从异步数据库 URL 创建同步引擎（供 Casbin 适配器使用）"""
    from app.config import settings
    from sqlalchemy import create_engine

    url = settings.DATABASE_URL
    # 将 asyncpg 驱动替换为 psycopg2
    sync_url = url.replace("+asyncpg", "+psycopg2")
    if "+psycopg2" not in sync_url and sync_url.startswith("postgresql"):
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")

    return create_engine(sync_url, pool_size=5, max_overflow=10)


async def get_enforcer() -> Enforcer:
    """获取 Casbin Enforcer 单例（线程安全 + 协程安全）"""
    global _enforcer
    if _enforcer is not None:
        return _enforcer

    async with _async_init_lock:
        if _enforcer is not None:
            return _enforcer

        with _enforcer_lock:
            if _enforcer is not None:
                return _enforcer

            try:
                from casbin_sqlalchemy_adapter import Adapter
                sync_engine = _create_sync_engine()
                adapter = Adapter(sync_engine)
                _enforcer = Enforcer(_get_model_path(), adapter)
                _enforcer.enable_auto_save(True)
                logger.info("Casbin Enforcer 初始化完成（PostgreSQL 适配器模式）")
            except Exception as e:
                logger.warning(f"Casbin 适配器初始化失败，回退到内存模式: {e}")
                _enforcer = Enforcer(_get_model_path())
                _enforcer.enable_auto_save(False)
                logger.info("Casbin Enforcer 初始化完成（内存模式）")

            return _enforcer


async def _is_superuser(user_id: int) -> bool:
    """检查用户是否为超级管理员（带缓存）
    API 密钥用户（负数 ID）永远不会是超级管理员。
    """
    if user_id < 0:
        return False
    with _superuser_cache_lock:
        if user_id in _superuser_cache:
            return _superuser_cache[user_id]

    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        stmt = select(User.is_superuser).where(User.id == user_id)
        result = await db.execute(stmt)
        is_super = result.scalar_one_or_none() or False

    with _superuser_cache_lock:
        _superuser_cache[user_id] = is_super
        # 限制缓存大小
        if len(_superuser_cache) > 1000:
            keys = list(_superuser_cache.keys())[:500]
            for k in keys:
                del _superuser_cache[k]

    return is_super


def _clear_superuser_cache():
    """清除超管缓存"""
    with _superuser_cache_lock:
        _superuser_cache.clear()


async def sync_policies(db: AsyncSession) -> None:
    """
    从数据库同步策略到 Casbin（双缓冲模式）。
    先构建新 Enforcer，验证无误后原子替换，避免策略真空。
    """
    # ---- 第一步：批量预加载所有数据 ----
    # 1. 所有活跃角色
    role_stmt = select(Role).where(Role.is_active == True)
    role_result = await db.execute(role_stmt)
    roles = list(role_result.scalars().all())
    role_id_to_code: dict[int, str] = {r.id: r.code for r in roles}

    # 2. 用户-角色关联
    ur_stmt = select(user_roles)
    ur_result = await db.execute(ur_stmt)
    ur_rows = ur_result.all()
    user_role_pairs: dict[int, set[str]] = {}
    for row in ur_rows:
        code = role_id_to_code.get(row.role_id)
        if code:
            user_role_pairs.setdefault(row.user_id, set()).add(code)

    # 3. 所有权限
    perm_stmt = select(Permission)
    perm_result = await db.execute(perm_stmt)
    permissions = list(perm_result.scalars().all())
    perm_id_to_code: dict[int, str] = {p.id: p.code for p in permissions}

    # 4. 角色-权限关联
    rp_stmt = select(role_permissions)
    rp_result = await db.execute(rp_stmt)
    rp_rows = rp_result.all()
    role_perm_map: dict[int, set[int]] = {}
    for row in rp_rows:
        role_perm_map.setdefault(row.role_id, set()).add(row.permission_id)

    # 5. 所有可见菜单
    menu_stmt = select(Menu).where(Menu.visible == True)
    menu_result = await db.execute(menu_stmt)
    menus = list(menu_result.scalars().all())
    menu_id_to_obj: dict[int, Menu] = {m.id: m for m in menus}

    # 6. 角色-菜单关联
    rm_stmt = select(role_menus)
    rm_result = await db.execute(rm_stmt)
    rm_rows = rm_result.all()
    role_menu_map: dict[int, set[int]] = {}
    for row in rm_rows:
        role_menu_map.setdefault(row.role_id, set()).add(row.menu_id)

    # 7. API 密钥-角色关联（活跃且有关联角色的密钥）
    api_key_stmt = select(ApiKey).where(
        ApiKey.is_active == True,
        ApiKey.role_id.isnot(None),
    )
    api_key_result = await db.execute(api_key_stmt)
    api_keys = list(api_key_result.scalars().all())
    api_key_role_pairs: list[tuple[int, str]] = []
    for ak in api_keys:
        role_code = role_id_to_code.get(ak.role_id)
        if role_code and (not ak.expires_at or ak.expires_at > datetime.now()):
            api_key_role_pairs.append((ak.id, role_code))

    # ---- 第二步：构建新 Enforcer ----
    new_enforcer = Enforcer(_get_model_path())
    new_enforcer.enable_auto_save(False)

    # 用户 -> 角色继承
    for uid, role_codes in user_role_pairs.items():
        for rc in role_codes:
            for dom in [DOMAIN_API, DOMAIN_MENU, DOMAIN_BUTTON]:
                new_enforcer.add_named_grouping_policy("g", f"user:{uid}", f"role:{rc}", dom)

    # API 密钥 -> 角色继承
    for ak_id, role_code in api_key_role_pairs:
        for dom in [DOMAIN_API, DOMAIN_MENU, DOMAIN_BUTTON]:
            new_enforcer.add_named_grouping_policy("g", f"user:api_key_{ak_id}", f"role:{role_code}", dom)

    # 角色 -> API 权限（仅来自 Permission 表）
    for role_id, perm_ids in role_perm_map.items():
        role_code = role_id_to_code.get(role_id)
        if not role_code:
            continue
        for pid in perm_ids:
            pcode = perm_id_to_code.get(pid)
            if pcode:
                new_enforcer.add_named_policy("p", f"role:{role_code}", DOMAIN_API, pcode, "access")

    # 角色 -> 菜单/按钮权限（仅来自 Menu 表）
    for role_id, menu_ids in role_menu_map.items():
        role_code = role_id_to_code.get(role_id)
        if not role_code:
            continue
        for mid in menu_ids:
            menu = menu_id_to_obj.get(mid)
            if not menu:
                continue
            if menu.menu_type == "button":
                perm_code = menu.permission or f"menu_btn:{mid}"
                new_enforcer.add_named_policy("p", f"role:{role_code}", DOMAIN_BUTTON, perm_code, "click")
            else:
                menu_path = menu.path or f"menu:{mid}"
                new_enforcer.add_named_policy("p", f"role:{role_code}", DOMAIN_MENU, menu_path, "access")

    # ---- 第三步：原子替换 + 持久化 ----
    global _enforcer
    with _enforcer_lock:
        old_enforcer = _enforcer
        _enforcer = new_enforcer

    # 持久化到数据库（如果使用适配器）
    try:
        _persist_policies_to_db()
        logger.info("Casbin 策略已持久化到 casbin_rule 表")
    except Exception as e:
        logger.warning(f"Casbin 策略持久化失败（不影响内存策略）: {e}")

    policy_count = len(new_enforcer.get_policy()) + len(new_enforcer.get_grouping_policy())
    logger.info(f"Casbin 策略同步完成: {len(user_role_pairs)} 个用户, {len(api_key_role_pairs)} 个API密钥, {policy_count} 条策略")


def _get_casbin_subject(user_id: int) -> str:
    """根据用户ID获取 Casbin 主体名称
    - 正整数 ID: 普通用户 → user:{user_id}
    - 负整数 ID: API 密钥 → user:api_key_{-user_id}
    """
    if user_id < 0:
        return f"user:api_key_{-user_id}"
    return f"user:{user_id}"


async def check_api_permission(user_id: int, permission_code: str) -> bool:
    """检查用户是否拥有指定 API 权限"""
    if await _is_superuser(user_id):
        return True
    enforcer = await get_enforcer()
    subject = _get_casbin_subject(user_id)
    return enforcer.enforce(subject, DOMAIN_API, permission_code, "access")


async def check_menu_permission(user_id: int, menu_path: str) -> bool:
    """检查用户是否拥有指定菜单权限"""
    if await _is_superuser(user_id):
        return True
    enforcer = await get_enforcer()
    subject = _get_casbin_subject(user_id)
    return enforcer.enforce(subject, DOMAIN_MENU, menu_path, "access")


async def check_button_permission(user_id: int, button_code: str) -> bool:
    """检查用户是否拥有指定按钮权限"""
    if await _is_superuser(user_id):
        return True
    enforcer = await get_enforcer()
    subject = _get_casbin_subject(user_id)
    return enforcer.enforce(subject, DOMAIN_BUTTON, button_code, "click")


async def get_user_api_permissions(user_id: int) -> List[str]:
    """获取用户所有 API 权限编码列表"""
    if await _is_superuser(user_id):
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Permission.code))
            return [r[0] for r in result.all()]

    enforcer = await get_enforcer()
    subject = _get_casbin_subject(user_id)
    roles = enforcer.get_roles_for_user_in_domain(subject, DOMAIN_API)
    perms = set()
    for role in roles:
        policies = enforcer.get_permissions_for_user_in_domain(role, DOMAIN_API)
        for p in policies:
            if len(p) >= 3 and p[1] == DOMAIN_API:
                perms.add(p[2])
    return list(perms)


async def get_user_menu_paths(user_id: int) -> List[str]:
    """获取用户所有可访问的菜单路径列表"""
    enforcer = await get_enforcer()
    subject = _get_casbin_subject(user_id)
    roles = enforcer.get_roles_for_user_in_domain(subject, DOMAIN_MENU)
    paths = set()
    for role in roles:
        policies = enforcer.get_permissions_for_user_in_domain(role, DOMAIN_MENU)
        for p in policies:
            if len(p) >= 3 and p[1] == DOMAIN_MENU:
                paths.add(p[2])
    return list(paths)


async def get_user_button_permissions(user_id: int) -> List[str]:
    """获取用户所有按钮权限编码列表"""
    if await _is_superuser(user_id):
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Menu.permission).where(Menu.menu_type == "button", Menu.visible == True, Menu.permission != None)
            )
            return [r[0] for r in result.all() if r[0]]

    enforcer = await get_enforcer()
    subject = _get_casbin_subject(user_id)
    roles = enforcer.get_roles_for_user_in_domain(subject, DOMAIN_BUTTON)
    perms = set()
    for role in roles:
        policies = enforcer.get_permissions_for_user_in_domain(role, DOMAIN_BUTTON)
        for p in policies:
            if len(p) >= 3 and p[1] == DOMAIN_BUTTON:
                perms.add(p[2])
    return list(perms)


async def get_user_menus(db: AsyncSession, user_id: int) -> list[dict]:
    """获取用户可见的菜单列表（使用 SQL IN 查询，避免全表扫描）"""
    from app.models.user import User

    # API 密钥用户（负数 ID）永远不会是超级用户
    if user_id < 0:
        is_superuser = False
    else:
        # 超级用户返回所有可见菜单
        user_stmt = select(User.is_superuser).where(User.id == user_id)
        result = await db.execute(user_stmt)
        is_superuser = result.scalar_one_or_none() or False

    if is_superuser:
        stmt = select(Menu).where(Menu.visible == True).order_by(Menu.sort)
        result = await db.execute(stmt)
        menus = list(result.scalars().all())
    else:
        menu_paths = await get_user_menu_paths(user_id)
        button_codes = await get_user_button_permissions(user_id)

        if not menu_paths and not button_codes:
            return []

        # 使用 SQL IN 精确查询，避免全表扫描
        or_conditions = []
        if menu_paths:
            or_conditions.append(
                (Menu.menu_type.in_(["directory", "menu"])) & (Menu.path.in_(menu_paths))
            )
        if button_codes:
            or_conditions.append(
                (Menu.menu_type == "button") & (Menu.permission.in_(button_codes))
            )

        stmt = select(Menu).where(
            Menu.visible == True,
            or_(*or_conditions)
        )
        result = await db.execute(stmt)
        menus = list(result.scalars().all())

        # 自动补全父目录
        parent_ids = {m.parent_id for m in menus if m.parent_id is not None}
        existing_ids = {m.id for m in menus}
        missing_ids = parent_ids - existing_ids
        if missing_ids:
            parent_stmt = select(Menu).where(Menu.id.in_(missing_ids), Menu.visible == True)
            parent_result = await db.execute(parent_stmt)
            menus.extend(parent_result.scalars().all())
            menus.sort(key=lambda m: m.sort)

    return [
        {
            "id": m.id, "name": m.name, "path": m.path, "component": m.component,
            "icon": m.icon, "menu_type": m.menu_type, "parent_id": m.parent_id,
            "sort": m.sort, "visible": m.visible, "permission": m.permission,
        }
        for m in menus
    ]


async def _get_redis():
    """获取 Redis 连接"""
    from app.utils.redis import get_redis
    return await get_redis()


async def _bump_policy_version() -> None:
    """递增 Redis 中的策略版本号（通知其他 Worker 重新加载）"""
    try:
        rd = await _get_redis()
        await rd.incr(POLICY_VERSION_KEY)
    except Exception as e:
        logger.warning(f"更新策略版本号失败: {e}")


async def _check_policy_version() -> bool:
    """检查策略版本是否已变更，如已变更则重新加载"""
    global _local_version
    try:
        rd = await _get_redis()
        remote_version = int(await rd.get(POLICY_VERSION_KEY) or 0)
        if remote_version > _local_version:
            _local_version = remote_version
            return True
    except Exception:
        pass
    return False


def _persist_policies_to_db() -> None:
    """将当前 Enforcer 的策略持久化到 casbin_rule 表"""
    try:
        from casbin_sqlalchemy_adapter import Adapter
        sync_engine = _create_sync_engine()
        adapter = Adapter(sync_engine)
        persist_enforcer = Enforcer(_get_model_path(), adapter)
        persist_enforcer.enable_auto_save(True)
        persist_enforcer.clear_policy()

        # 将当前内存策略写入持久化 Enforcer
        for p in _enforcer.get_policy():
            persist_enforcer.add_policy(p)
        for gp in _enforcer.get_named_grouping_policy("g"):
            persist_enforcer.add_named_grouping_policy("g", gp)

        persist_enforcer.save_policy()
    except Exception as e:
        logger.warning(f"Casbin 策略持久化失败（不影响内存策略）: {e}")


def _sync_single_api_key_policy_db(subject: str, role_code: str | None) -> None:
    """在 casbin_rule 表中增量更新单个 API Key 的继承策略（单事务，避免全表重写）"""
    sync_engine = _create_sync_engine()
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM casbin_rule WHERE ptype = 'g' AND v0 = :subject"),
                {"subject": subject},
            )
            if role_code:
                for dom in [DOMAIN_API, DOMAIN_MENU, DOMAIN_BUTTON]:
                    conn.execute(
                        text(
                            "INSERT INTO casbin_rule (ptype, v0, v1, v2) "
                            "VALUES ('g', :subject, :role, :dom)"
                        ),
                        {"subject": subject, "role": f"role:{role_code}", "dom": dom},
                    )
    except Exception as e:
        logger.warning(f"Casbin API Key 策略增量持久化失败: {e}")
    finally:
        sync_engine.dispose()


async def update_api_key_policy(api_key_id: int, role_code: str | None) -> None:
    """
    轻量级更新单个 API Key 的 Casbin 策略（不触发全量同步）。
    删除旧策略，如果 role_code 不为 None 则添加新策略，然后持久化 + 版本号递增。
    """
    enforcer = await get_enforcer()
    subject = f"user:api_key_{api_key_id}"

    with _enforcer_lock:
        # 移除该 API Key 的所有现有策略
        for dom in [DOMAIN_API, DOMAIN_MENU, DOMAIN_BUTTON]:
            enforcer.remove_filtered_named_grouping_policy("g", 0, subject)

        # 添加新策略
        if role_code:
            for dom in [DOMAIN_API, DOMAIN_MENU, DOMAIN_BUTTON]:
                enforcer.add_named_grouping_policy("g", subject, f"role:{role_code}", dom)

    # 增量持久化到数据库（单事务直接 SQL，避免全表重写）
    _sync_single_api_key_policy_db(subject, role_code)

    # 版本号递增（通知其他 Worker 重新加载）
    await _bump_policy_version()


async def _reload_if_stale(db: AsyncSession) -> None:
    """如果策略版本过期，从 casbin_rule 表重新加载"""
    if await _check_policy_version():
        enforcer = await get_enforcer()
        try:
            enforcer.load_policy()
            logger.info("Casbin 策略已从数据库重新加载（版本过期）")
        except Exception as e:
            logger.warning(f"从数据库重新加载策略失败，改用全量同步: {e}")
            await sync_policies(db)


async def invalidate_policy(db: AsyncSession) -> None:
    """权限变更时调用：同步策略 + 持久化 + 通知其他 Worker"""
    global _local_version
    _clear_superuser_cache()
    await sync_policies(db)
    await _bump_policy_version()
    try:
        rd = await _get_redis()
        _local_version = int(await rd.get(POLICY_VERSION_KEY) or 0)
    except Exception:
        pass
    logger.info("Casbin 策略已重新同步并持久化")


async def ensure_policy_loaded(db: AsyncSession) -> None:
    """确保策略已加载（启动时或版本过期时调用）"""
    if _enforcer is None:
        await get_enforcer()
        await sync_policies(db)
        try:
            rd = await _get_redis()
            version = int(await rd.get(POLICY_VERSION_KEY) or 0)
            global _local_version
            _local_version = version
        except Exception:
            pass
    else:
        await _reload_if_stale(db)
