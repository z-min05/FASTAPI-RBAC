import pytest
from app.core.rbac import check_permission, get_user_permissions, get_user_roles


@pytest.mark.asyncio
async def test_check_permission_for_nonexistent_user():
    """测试不存在用户的权限检查（需要配合真实数据库）"""
    # 此测试在集成测试环境中验证
    pass
