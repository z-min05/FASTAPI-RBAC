import time
import json
import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy import select
from app.utils.logger import logger
from app.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.operation_log import OperationLog
from app.models.user import User
from jose import JWTError

# 含明文凭据的认证接口：完全不写入操作日志（登录/注册）
AUTH_EXCLUDED_SUFFIXES = ("/auth/login", "/auth/register")
# 请求体中密码类字段一律脱敏，避免明文入库
_SENSITIVE_RE = re.compile(r'"(?:"?password|old_password|new_password|confirm_password)"?\s*:\s*"', re.IGNORECASE)


def _mask_sensitive(body: str | None) -> str | None:
    """将请求体 JSON 中 password 类字段的值替换为 ***（非 JSON 时正则兜底）。"""
    if not body:
        return body
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return _SENSITIVE_RE.sub(lambda m: m.group(0) + "***", body)

    def walk(obj):
        if isinstance(obj, dict):
            return {
                k: ("***" if isinstance(v, str) and "password" in k.lower() else walk(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [walk(item) for item in obj]
        return obj

    return json.dumps(walk(data), ensure_ascii=False)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志 / 操作审计中间件：非 GET 请求写入数据库"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 读取请求体
        body = None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                raw = await request.body()
                body = raw.decode("utf-8")[:4000] if raw else None
            except Exception:
                body = None

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        duration = int((time.time() - start_time) * 1000)

        # 只处理 API 请求
        path = request.url.path
        if not path.startswith("/api"):
            return response

        # 登录/注册等含明文凭据的接口不进入操作日志
        exclude_audit = path.endswith(AUTH_EXCLUDED_SUFFIXES)

        # 从 JWT 获取用户 ID（不再查数据库获取用户名）
        user_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = decode_token(token)
                if payload.get("type") == "access":
                    user_id = payload.get("sub")
            except JWTError:
                pass

        # 捕获响应体
        response_body = None
        # SSE（text/event-stream）等流式响应直接透传：
        # 若在此处消费 response.body_iterator，会先把整条流在服务端缓冲，
        # 并且重建响应时只保留前 4000 字符——SSE 末尾的 done 事件会被截掉，
        # 导致前端永远等不到流结束。因此流式响应不做响应体捕获/重建。
        content_type = response.headers.get("content-type", "")
        if request.method != "GET" and not exclude_audit and "text/event-stream" not in content_type:
            try:
                # 读取 response body chunks
                body_chunks = []
                async for chunk in response.body_iterator:
                    if isinstance(chunk, str):
                        body_chunks.append(chunk)
                    else:
                        body_chunks.append(chunk.decode("utf-8", errors="replace"))

                response_body = "".join(body_chunks)[:4000]

                # 重建 response，因为 body 已被消费
                from starlette.responses import Response as StarletteResponse
                new_response = StarletteResponse(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
                response = new_response
            except Exception:
                response_body = None

        # 控制台日志
        log_data = {
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration,
            "client_ip": request.client.host if request.client else None,
        }
        logger.info(json.dumps(log_data, ensure_ascii=False))

        # 非 GET 请求写入数据库（登录/注册除外）
        if request.method != "GET" and not exclude_audit:
            try:
                async with AsyncSessionLocal() as db:
                    # 回填用户名，保证审计日志能正确记录操作人
                    username = None
                    if user_id is not None:
                        result = await db.execute(
                            select(User.username).where(User.id == int(user_id))
                        )
                        username = result.scalar_one_or_none()
                    log_entry = OperationLog(
                        user_id=int(user_id) if user_id else None,
                        username=username,
                        method=request.method,
                        path=path,
                        params=_mask_sensitive(body),
                        status_code=response.status_code,
                        ip=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent", "")[:255],
                        duration=duration,
                        message=f"{request.method} {path} -> {response.status_code}",
                        response=response_body,
                    )
                    db.add(log_entry)
                    await db.commit()
            except Exception as e:
                logger.error(f"写入操作日志失败: {e}")

        return response
