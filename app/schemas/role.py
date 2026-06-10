from datetime import datetime
from pydantic import BaseModel, Field


class RoleBriefResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    sort: int = 0
    is_active: bool = True


class RoleCreate(RoleBase):
    permission_ids: list[int] | None = None
    menu_ids: list[int] | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    sort: int | None = None
    is_active: bool | None = None
    permission_ids: list[int] | None = None
    menu_ids: list[int] | None = None


class RoleResponse(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleWithPermissionsResponse(RoleResponse):
    permissions: list["PermissionBriefResponse"] = []
    menus: list["MenuBriefResponse"] = []

    model_config = {"from_attributes": True}


from app.schemas.permission import PermissionBriefResponse
from app.schemas.menu import MenuBriefResponse
RoleWithPermissionsResponse.model_rebuild()
