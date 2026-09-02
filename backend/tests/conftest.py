import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.db.session import get_db
from app.main import app

# 测试数据库（SQLite 内存）
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session
        await session.commit()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient):
    """注册用户并直接签发 token（测试环境绕过验证码登录）"""
    await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "test123456",
    })
    from sqlalchemy import select
    from app.models.user import User
    from app.security import create_access_token
    async with TestSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.username == "testuser"))
        ).scalar_one()
        return create_access_token(data={"sub": str(user.id)})


@pytest_asyncio.fixture
def auth_headers(auth_token: str):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture
async def superuser_token(client: AsyncClient):
    """注册超管用户并签发 token（用于需权限校验的接口测试）"""
    await client.post("/api/v1/auth/register", json={
        "username": "superadmin",
        "email": "super@example.com",
        "password": "test123456",
    })
    from sqlalchemy import select
    from app.models.user import User
    from app.security import create_access_token
    async with TestSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.username == "superadmin"))
        ).scalar_one()
        user.is_superuser = True
        await session.commit()
        return create_access_token(data={"sub": str(user.id)})


@pytest_asyncio.fixture
def superuser_headers(superuser_token: str):
    return {"Authorization": f"Bearer {superuser_token}"}
