import logging

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.middlewares.logging as logging_middleware
from app.middlewares.logging import LoggingMiddleware
from app.models.operation_log import OperationLog


test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """覆盖全局测试库建表，仅创建当前测试所需的操作日志表。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(OperationLog.__table__.create)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(OperationLog.__table__.drop)
    await test_engine.dispose()


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(LoggingMiddleware)

    @test_app.post("/api/v1/_test/unhandled-error")
    async def unhandled_error():
        raise RuntimeError("boom")

    @test_app.post("/api/v1/_test/business-error")
    async def business_error():
        # 模拟 HTTP 200，但统一响应体中 code=500 的业务错误。
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "业务处理失败", "data": None},
        )

    return test_app


@pytest.mark.asyncio
async def test_unhandled_error_is_logged_and_audited(monkeypatch, caplog):
    monkeypatch.setattr(logging_middleware, "AsyncSessionLocal", TestSessionLocal)
    transport = ASGITransport(
        app=_build_test_app(),
        raise_app_exceptions=False,
    )

    with caplog.at_level(logging.ERROR, logger="fastapi-rbac"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/_test/unhandled-error",
                json={"operation": "create"},
            )

    assert response.status_code == 500
    assert "请求处理异常" in caplog.text
    assert "RuntimeError: boom" in caplog.text
    assert "/api/v1/_test/unhandled-error" in caplog.text

    async with TestSessionLocal() as session:
        log = (
            await session.execute(
                select(OperationLog).where(
                    OperationLog.path == "/api/v1/_test/unhandled-error"
                )
            )
        ).scalar_one()

    assert log.status_code == 500
    assert log.method == "POST"
    assert "RuntimeError: boom" in log.message
    assert "Internal Server Error" in log.response
    assert '"operation": "create"' in log.params


@pytest.mark.asyncio
async def test_business_code_500_is_audited_as_failure(monkeypatch, caplog):
    monkeypatch.setattr(logging_middleware, "AsyncSessionLocal", TestSessionLocal)
    transport = ASGITransport(app=_build_test_app())

    with caplog.at_level(logging.ERROR, logger="fastapi-rbac"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/_test/business-error")

    assert response.status_code == 200
    assert '"status_code": 500' in caplog.text
    assert '"http_status_code": 200' in caplog.text

    async with TestSessionLocal() as session:
        log = (
            await session.execute(
                select(OperationLog).where(
                    OperationLog.path == "/api/v1/_test/business-error"
                )
            )
        ).scalar_one()

    assert log.status_code == 500
    assert "HTTP 200" in log.message
    assert "业务处理失败" in log.message
    assert '"code": 500' in log.response
