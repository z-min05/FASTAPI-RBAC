import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.utils.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志 / 操作审计中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        duration = int((time.time() - start_time) * 1000)

        # 记录请求日志
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                log_data["params"] = body.decode("utf-8")[:2000] if body else None
            except Exception:
                pass

        logger.info(json.dumps(log_data, ensure_ascii=False))

        return response
