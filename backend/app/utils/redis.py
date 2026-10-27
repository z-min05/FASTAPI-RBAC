import uuid

import redis.asyncio as redis

from app.config import settings
from app.utils.logger import logger

_redis: redis.Redis | None = None

_LOCK_PREFIX = "fa:lock:"
# 仅当锁值仍是自己的 token 时才删除，避免误删他人/下一轮的锁
_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


async def acquire_lock(name: str, ttl_seconds: int) -> str | None:
    """获取跨进程互斥锁。

    返回 token 表示加锁成功（释放时需带同一个 token）；
    返回 None 表示锁已被其他进程/请求占用；
    返回空串表示 Redis 不可用，已降级为“无锁放行”（维持原有单进程行为）。
    """
    token = uuid.uuid4().hex
    try:
        client = await get_redis()
        acquired = await client.set(
            f"{_LOCK_PREFIX}{name}", token, nx=True, ex=ttl_seconds
        )
    except Exception as e:
        logger.warning(f"[分布式锁] Redis 不可用，降级为无锁执行 name={name}: {e}")
        return ""
    return token if acquired else None


async def release_lock(name: str, token: str) -> None:
    """释放锁；token 不匹配时不做任何操作（锁已过期并被他人获取）"""
    if not token:
        return
    try:
        client = await get_redis()
        await client.eval(_RELEASE_LOCK_SCRIPT, 1, f"{_LOCK_PREFIX}{name}", token)
    except Exception as e:
        logger.warning(f"[分布式锁] 释放失败 name={name}: {e}")
