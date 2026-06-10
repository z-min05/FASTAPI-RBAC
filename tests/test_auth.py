import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "test123456",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "access_token" in data["data"]


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    # 先注册
    await client.post("/api/v1/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "test123456",
    })
    # 再登录
    response = await client.post("/api/v1/auth/login", json={
        "username": "loginuser",
        "password": "test123456",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "username": "nonexist",
        "password": "wrong",
    })
    assert response.status_code == 401
