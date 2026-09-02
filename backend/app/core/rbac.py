"""
旧的 RBAC 模块已被 Casbin 权限服务替代。
所有权限校验逻辑已迁移到 app.core.casbin_service.py。
此文件保留仅为兼容性引用，不应在新代码中使用。
"""

# 兼容性引用：role_service.py 中可能还有旧引用
from app.core.casbin_service import invalidate_policy as invalidate_user_cache
from app.core.casbin_service import get_user_menus
from app.core.casbin_service import get_user_api_permissions as get_user_permissions
from app.core.casbin_service import check_api_permission as check_permission
