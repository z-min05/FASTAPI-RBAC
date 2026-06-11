import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.utils.logger import logger
from app.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.operation_log import OperationLog
from jose import JWTError


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

        # 获取用户信息
        user_id = None
        username = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = decode_token(token)
                if payload.get("type") == "access":
                    user_id = payload.get("sub")
                    if user_id:
                        try:
                            from app.repositories.user_repo import UserRepository
                            async with AsyncSessionLocal() as db:
                                repo = UserRepository(db)
                                user = await repo.get_by_id(int(user_id))
                                if user:
                                    username = user.username
                        except Exception:
                            pass
            except JWTError:
                pass

        # 捕获响应体
        response_body = None
        if request.method != "GET":
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

        # 非 GET 请求写入数据库
        if request.method != "GET":
            try:
                async with AsyncSessionLocal() as db:
                    log_entry = OperationLog(
                        user_id=int(user_id) if user_id else None,
                        username=username,
                        method=request.method,
                        path=path,
                        params=body,
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
