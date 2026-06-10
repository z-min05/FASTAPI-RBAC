from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.middlewares.cors import add_cors_middleware
from app.middlewares.logging import LoggingMiddleware
from app.exceptions import AppException, app_exception_handler, validation_exception_handler
from app.api.v1 import router as v1_router
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} 启动中...")
    yield
    logger.info(f"{settings.APP_NAME} 关闭中...")


app = FastAPI(
    title=settings.APP_NAME,
    description="基于 FastAPI 的 RBAC 权限管理系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 中间件
add_cors_middleware(app)
app.add_middleware(LoggingMiddleware)

# 异常处理
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 路由
app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "ok"}


@app.get("/", tags=["根路径"])
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}
