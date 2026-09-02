import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_projects_unauthorized(client: AsyncClient):
    """未登录访问项目接口应返回 401"""
    response = await client.get("/api/v1/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_project_crud(client: AsyncClient, superuser_headers: dict):
    """超管：项目新增/列表/详情/编辑/删除全流程"""
    # 创建
    resp = await client.post("/api/v1/projects", headers=superuser_headers, json={
        "code": "PROJ-001",
        "name": "水表抄读项目",
        "description": "业务数据传输测试",
        "is_active": True,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    project_id = data["id"]
    assert data["code"] == "PROJ-001"

    # 编码重复应返回 409
    resp = await client.post("/api/v1/projects", headers=superuser_headers, json={
        "code": "PROJ-001",
        "name": "重复项目",
    })
    assert resp.status_code == 409

    # 列表
    resp = await client.get("/api/v1/projects", headers=superuser_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    # 关键字筛选
    resp = await client.get("/api/v1/projects", headers=superuser_headers, params={"keyword": "抄读"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1

    # 全部项目下拉
    resp = await client.get("/api/v1/projects/all", headers=superuser_headers)
    assert resp.status_code == 200
    assert any(p["id"] == project_id for p in resp.json()["data"])

    # 详情
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=superuser_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "水表抄读项目"

    # 编辑
    resp = await client.put(f"/api/v1/projects/{project_id}", headers=superuser_headers, json={
        "name": "水表抄读项目-改",
        "is_active": False,
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "水表抄读项目-改"
    assert resp.json()["data"]["is_active"] is False

    # 删除
    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=superuser_headers)
    assert resp.status_code == 200

    # 删除后详情应为 404
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=superuser_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_with_testcases_conflict(client: AsyncClient, superuser_headers: dict):
    """项目下存在用例时删除应返回 409"""
    resp = await client.post("/api/v1/projects", headers=superuser_headers, json={
        "code": "PROJ-CONFLICT",
        "name": "有关联用例的项目",
    })
    project_id = resp.json()["data"]["id"]

    await client.post("/api/v1/testcases", headers=superuser_headers, json={
        "project_id": project_id,
        "title": "登录成功",
        "module": "auth",
        "priority": "P0",
        "expected_result": "返回 200",
    })
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=superuser_headers)
    assert resp.status_code == 409
