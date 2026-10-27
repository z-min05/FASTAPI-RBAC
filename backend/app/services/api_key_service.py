import hashlib
import secrets
from datetime import datetime

from math import ceil
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import NotFoundException


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


def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return user.nickname or user.username


def _owner_filter(owner_id: int):
    """归属筛选：新密钥看 user_id；历史密钥 user_id 为空时回退到 created_by"""
    return or_(
        ApiKey.user_id == owner_id,
        and_(ApiKey.user_id.is_(None), ApiKey.created_by == owner_id),
    )


class ApiKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def paginate(self, params: PaginationParams, owner_id: int) -> PaginatedResponse:
        """分页查询当前用户归属的 API 密钥列表"""
        owner_cond = _owner_filter(owner_id)
        count_stmt = select(func.count(ApiKey.id)).select_from(ApiKey).where(owner_cond)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(ApiKey)
            .where(owner_cond)
            .order_by(ApiKey.id.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        keys = list((await self.db.execute(stmt)).scalars().all())

        # 批量取归属用户显示名（含历史密钥回退到创建人）
        owner_ids = {k.user_id or k.created_by for k in keys}
        owner_ids.discard(None)
        owner_map: dict[int, User] = {}
        if owner_ids:
            user_stmt = select(User).where(User.id.in_(owner_ids))
            owner_map = {u.id: u for u in (await self.db.execute(user_stmt)).scalars().all()}

        items = []
        for key in keys:
            owner_id = key.user_id or key.created_by
            items.append({
                "id": key.id,
                "name": key.name,
                "key_prefix": key.key_prefix,
                "user_id": owner_id,
                "user_name": _user_display_name(owner_map.get(owner_id)),
                "expires_at": key.expires_at,
                "is_active": key.is_active,
                "last_used_at": key.last_used_at,
                "created_at": key.created_at,
                "updated_at": key.updated_at,
            })

        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=ceil(total / params.page_size) if total > 0 else 0,
        )

    async def get_by_id(self, key_id: int, owner_id: int) -> ApiKey:
        """取当前用户归属的密钥；非本人密钥按不存在处理，避免越权探测"""
        key = await self.db.get(ApiKey, key_id)
        if not key or (key.user_id or key.created_by) != owner_id:
            raise NotFoundException("API 密钥不存在")
        return key

    async def create(self, data: ApiKeyCreate, owner: User) -> tuple[ApiKey, str]:
        """为当前用户创建 API 密钥，返回 (ApiKey, full_key)

        密钥的权限、操作人、责任人全部等同归属用户本人。
        """
        full_key, key_hash, key_prefix = _generate_key()

        api_key = ApiKey(
            name=data.name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=owner.id,
            expires_at=data.expires_at,
            is_active=True,
            created_by=owner.id,
        )
        self.db.add(api_key)
        await self.db.flush()
        # refresh 取回服务端生成的 created_at/updated_at，避免异步环境惰性加载报错
        await self.db.refresh(api_key)
        return api_key, full_key

    async def update_status(self, key_id: int, is_active: bool, owner_id: int) -> ApiKey:
        """启用/禁用当前用户的 API 密钥"""
        api_key = await self.get_by_id(key_id, owner_id)
        if api_key.is_active == is_active:
            return api_key

        api_key.is_active = is_active
        await self.db.flush()
        # refresh 重新加载服务端生成的 updated_at，避免异步环境惰性加载报错
        await self.db.refresh(api_key)
        return api_key

    async def delete(self, key_id: int, owner_id: int) -> None:
        api_key = await self.get_by_id(key_id, owner_id)
        await self.db.delete(api_key)
        await self.db.flush()

    async def regenerate(self, key_id: int, owner_id: int) -> tuple[ApiKey, str]:
        """重新生成当前用户的密钥，返回 (ApiKey, full_key)
        仅重新生成密钥哈希，归属用户不变。
        """
        api_key = await self.get_by_id(key_id, owner_id)
        full_key, key_hash, key_prefix = _generate_key()
        api_key.key_hash = key_hash
        api_key.key_prefix = key_prefix
        await self.db.flush()
        return api_key, full_key

    @classmethod
    async def validate_key(cls, db: AsyncSession, raw_key: str) -> ApiKey | None:
        """验证 API 密钥，返回 ApiKey 对象或 None"""
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
