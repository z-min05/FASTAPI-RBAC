import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_users_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/users")
    assert response.status_code == 401
