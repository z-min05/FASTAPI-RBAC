import time
import json
import re
import hashlib
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse
from sqlalchemy import select
from app.utils.logger import logger
from app.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.operation_log import OperationLog
from app.models.api_key import ApiKey
from app.models.user import User
from jose import JWTError

# 含明文凭据的认证接口：完全不写入操作日志（登录/注册）
AUTH_EXCLUDED_SUFFIXES = ("/auth/login", "/auth/register")
# 请求体中密码类字段一律脱敏，避免明文入库
_SENSITIVE_RE = re.compile(r'"(?:"?password|old_password|new_password|confirm_password)"?\s*:\s*"', re.IGNORECASE)
# 响应/请求体中可能出现明文密钥/令牌的字段名（键名包含即脱敏，值仅限字符串）
_SENSITIVE_KEY_RE = re.compile(
    r"password|full_key|api_key|key_hash|secret|access_token|refresh_token|token", re.IGNORECASE
)


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


def _mask_secret_values(content: str | None) -> str | None:
    """将 JSON 文本中密钥/令牌类字段的字符串值替换为 ***。

    仅用于日志落库：响应体仍需原样返回给客户端（如创建成功需展示完整密钥），
    因此脱敏发生在写入 operation_logs 之前，不影响返回给前端的原始内容。
    """
    if not content:
        return content
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content

    def walk(obj):
        if isinstance(obj, dict):
            return {
                k: ("***" if isinstance(v, str) and _SENSITIVE_KEY_RE.search(k) else walk(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [walk(item) for item in obj]
        return obj

    return json.dumps(walk(data), ensure_ascii=False)


def _parse_json_object(content: str | None) -> dict[str, Any] | None:
    if not content:
        return None
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _effective_status(http_status: int, response_body: str | None) -> int:
    """优先使用 HTTP 状态码；兼容 HTTP 200 + 业务 code=5xx 的响应。"""
    if http_status >= 400:
        return http_status
    data = _parse_json_object(response_body)
    code = data.get("code") if data else None
    if isinstance(code, int) and 400 <= code <= 599:
        return code
    if isinstance(code, str) and code.isdigit() and 400 <= int(code) <= 599:
        return int(code)
    return http_status


def _response_error_message(response_body: str | None) -> str | None:
    data = _parse_json_object(response_body)
    if not data:
        return None
    message = data.get("message") or data.get("detail")
    return str(message)[:1000] if message else None


def _exception_summary(exc: Exception) -> str:
    detail = str(exc).strip()
    summary = type(exc).__name__ + (f": {detail}" if detail else "")
    return summary[:1000]


async def _resolve_operator(auth_header: str, db) -> tuple[int | None, str | None]:
    """解析请求操作者身份，返回 (user_id, 显示名)。

    - JWT（登录用户）：真实 user_id + 用户名
    - API Key（sk- 前缀）：user_id 存负值 -(api_key.id)（与虚拟用户约定一致，
      operation_logs.user_id 无外键可存），显示名形如 "API密钥(密钥名)"
    - 无法识别：None, None（仍会落库一条匿名记录）
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None
    token = auth_header[len("Bearer "):].strip()
    if not token:
        return None, None

    # API Key 识别
    if token.startswith("sk-"):
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            select(ApiKey.id, ApiKey.name).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        row = result.first()
        if row:
            return -(row[0]), f"API密钥({row[1]})"[:50]
        return None, None

    # JWT 识别
    try:
        payload = decode_token(token)
    except JWTError:
        return None, None
    if payload.get("type") != "access":
        return None, None
    user_id = payload.get("sub")
    if user_id is None:
        return None, None
    username_result = await db.execute(
        select(User.username).where(User.id == int(user_id))
    )
    username = username_result.scalar_one_or_none()
    return int(user_id), username


async def _write_operation_log(
    *,
    request: Request,
    body: str | None,
    response_body: str | None,
    status_code: int,
    http_status_code: int,
    duration: int,
    message: str,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            user_id, username = await _resolve_operator(
                request.headers.get("authorization", ""), db
            )
            log_entry = OperationLog(
                user_id=user_id,
                username=username,
                method=request.method,
                path=request.url.path,
                params=_mask_sensitive(body),
                status_code=status_code,
                ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:255],
                duration=duration,
                message=message[:2000],
                response=_mask_secret_values(response_body),
            )
            db.add(log_entry)
            await db.commit()
    except Exception:
        logger.exception(
            "写入操作日志失败 method=%s path=%s http_status=%s status=%s",
            request.method,
            request.url.path,
            http_status_code,
            status_code,
        )


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
        try:
            response = await call_next(request)
        except Exception as exc:
            duration = int((time.time() - start_time) * 1000)
            path = request.url.path
            error_summary = _exception_summary(exc)
            log_data = {
                "method": request.method,
                "path": path,
                "status_code": 500,
                "http_status_code": 500,
                "duration_ms": duration,
                "client_ip": request.client.host if request.client else None,
                "error": error_summary,
            }
            logger.exception(
                "请求处理异常 %s",
                json.dumps(log_data, ensure_ascii=False),
            )

            if path.startswith("/api") and not path.endswith(AUTH_EXCLUDED_SUFFIXES):
                if request.method != "GET":
                    error_body = json.dumps(
                        {"code": 500, "message": "Internal Server Error", "data": None},
                        ensure_ascii=False,
                    )
                    await _write_operation_log(
                        request=request,
                        body=body,
                        response_body=error_body,
                        status_code=500,
                        http_status_code=500,
                        duration=duration,
                        message=f"{request.method} {path} -> 500 ({error_summary})",
                    )
            # 继续抛出，交给 FastAPI/Starlette 生成原有的 500 响应。
            raise

        # 计算耗时
        duration = int((time.time() - start_time) * 1000)

        # 只处理 API 请求
        path = request.url.path
        if not path.startswith("/api"):
            return response

        # 登录/注册等含明文凭据的接口不进入操作日志
        exclude_audit = path.endswith(AUTH_EXCLUDED_SUFFIXES)

        # 捕获响应体
        response_body = None
        # SSE（text/event-stream）等流式响应直接透传：
        # 若在此处消费 response.body_iterator，会先把整条流在服务端缓冲，
        # 并且重建响应时只保留前 4000 字符——SSE 末尾的 done 事件会被截掉，
        # 导致前端永远等不到流结束。因此流式响应不做响应体捕获/重建。
        content_type = response.headers.get("content-type", "")
        response_exception: Exception | None = None
        if request.method != "GET" and not exclude_audit and "text/event-stream" not in content_type:
            try:
                # 读取 response body chunks
                body_chunks = []
                async for chunk in response.body_iterator:
                    if isinstance(chunk, str):
                        body_chunks.append(chunk)
                    else:
                        body_chunks.append(chunk.decode("utf-8", errors="replace"))

                full_body = "".join(body_chunks)
                # 仅审计落库做截断，返回给前端的必须是完整内容
                response_body = full_body[:4000]

                # 重建 response，因为 body 已被消费。
                # 必须剔除原 content-length：Starlette 只在该头缺失时才会按新 body
                # 重算（见 starlette/responses.py 的 init_headers），否则头部声明的
                # 长度与实际 body 不一致，浏览器会报 net::ERR_CONTENT_LENGTH_MISMATCH。
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() != "content-length"
                }
                new_response = StarletteResponse(
                    content=full_body,
                    status_code=response.status_code,
                    headers=headers,
                    media_type=response.media_type,
                )
                response = new_response
            except Exception as exc:
                response_exception = exc
                response_body = None

        http_status_code = response.status_code
        status_code = _effective_status(http_status_code, response_body)
        error_message = (
            _response_error_message(response_body) if status_code >= 400 else None
        )
        if response_exception is not None:
            status_code = 500
            http_status_code = 500
            error_message = _exception_summary(response_exception)

        # 控制台日志
        log_data = {
            "method": request.method,
            "path": path,
            "status_code": status_code,
            "http_status_code": http_status_code,
            "duration_ms": duration,
            "client_ip": request.client.host if request.client else None,
        }
        if error_message:
            log_data["error"] = error_message
        if response_exception is not None:
            logger.exception(
                "读取响应流异常 %s",
                json.dumps(log_data, ensure_ascii=False),
                exc_info=(
                    type(response_exception),
                    response_exception,
                    response_exception.__traceback__,
                ),
            )
        elif status_code >= 500:
            logger.error(json.dumps(log_data, ensure_ascii=False))
        else:
            logger.info(json.dumps(log_data, ensure_ascii=False))

        # 非 GET 请求写入数据库（登录/注册除外）
        if request.method != "GET" and not exclude_audit:
            message = f"{request.method} {path} -> {status_code}"
            if http_status_code != status_code:
                message += f" (HTTP {http_status_code})"
            if error_message:
                message += f" ({error_message})"
            await _write_operation_log(
                request=request,
                body=body,
                response_body=response_body,
                status_code=status_code,
                http_status_code=http_status_code,
                duration=duration,
                message=message,
            )

        if response_exception is not None:
            raise response_exception

        return response
