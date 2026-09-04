import hashlib
import secrets
from datetime import datetime

from math import ceil
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.role import Role
from app.schemas.api_key import ApiKeyCreate
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.casbin_service import update_api_key_policy
from app.exceptions import NotFoundException, BadRequestException


def _generate_key() -> tuple[str, str, str]:
    """生成 API 密钥，返回 (full_key, key_hash, key_prefix)"""
    random_part = secrets.token_urlsafe(32)
    full_key = f"sk-{random_part}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:10]  # 如 "sk-ABC123..."
    return full_key, key_hash, key_prefix


def _hash_key(key: str) -> str:
    """对密钥进行哈希（用于验证）"""
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def paginate(self, params: PaginationParams) -> PaginatedResponse:
        """分页查询 API 密钥列表"""
        # 总数
        count_stmt = select(func.count(ApiKey.id)).select_from(ApiKey)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页
        stmt = (
            select(ApiKey)
            .order_by(ApiKey.id.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        result = await self.db.execute(stmt)
        keys = list(result.scalars().all())

        return PaginatedResponse(
            items=keys,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=ceil(total / params.page_size) if total > 0 else 0,
        )

    async def get_by_id(self, key_id: int) -> ApiKey:
        key = await self.db.get(ApiKey, key_id)
        if not key:
            raise NotFoundException("API 密钥不存在")
        return key

    async def create(self, data: ApiKeyCreate, created_by: int) -> tuple[ApiKey, str]:
        """创建 API 密钥，返回 (ApiKey, full_key)"""
        role = await self.db.get(Role, data.role_id)
        if not role:
            raise NotFoundException("角色不存在")

        full_key, key_hash, key_prefix = _generate_key()

        api_key = ApiKey(
            name=data.name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            role_id=data.role_id,
            expires_at=data.expires_at,
            is_active=True,
            created_by=created_by,
        )
        self.db.add(api_key)
        await self.db.flush()
        # 轻量级更新 Casbin 策略
        await update_api_key_policy(api_key.id, role.code)
        return api_key, full_key

    async def update_status(self, key_id: int, is_active: bool) -> ApiKey:
        """启用/禁用 API 密钥"""
        api_key = await self.get_by_id(key_id)
        if api_key.is_active == is_active:
            return api_key

        api_key.is_active = is_active
        await self.db.flush()
        # refresh 重新加载服务端生成的 updated_at，避免异步环境惰性加载报错
        await self.db.refresh(api_key)

        # 同步 Casbin 策略：禁用则移除权限，启用则恢复角色权限
        role_code = None
        if is_active and api_key.role_id:
            role = await self.db.get(Role, api_key.role_id)
            role_code = role.code if role else None
        await update_api_key_policy(key_id, role_code)
        return api_key

    async def delete(self, key_id: int) -> None:
        api_key = await self.get_by_id(key_id)
        await self.db.delete(api_key)
        await self.db.flush()
        # 移除 Casbin 策略
        await update_api_key_policy(key_id, None)

    async def regenerate(self, key_id: int) -> tuple[ApiKey, str]:
        """重新生成密钥，返回 (ApiKey, full_key)
        仅重新生成密钥哈希，角色不变，无需更新 Casbin 策略。
        """
        api_key = await self.get_by_id(key_id)
        full_key, key_hash, key_prefix = _generate_key()
        api_key.key_hash = key_hash
        api_key.key_prefix = key_prefix
        await self.db.flush()
        return api_key, full_key

    @classmethod
    async def validate_key(cls, db: AsyncSession, raw_key: str) -> ApiKey | None:
        """验证 API 密钥，返回 ApiKey 对象（含有效角色）或 None"""
        key_hash = _hash_key(raw_key)
        stmt = select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,
        )
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None

        # 检查是否过期
        if api_key.expires_at and api_key.expires_at < datetime.now():
            return None

        # 更新最后使用时间
        api_key.last_used_at = datetime.now()
        await db.flush()
        return api_key