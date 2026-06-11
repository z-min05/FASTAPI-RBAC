from datetime import datetime
from pydantic import BaseModel, Field


class PermissionBriefResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}


class PermissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    module: str | None = None
    action: str | None = None


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    module: str | None = None
    action: str | None = None


class PermissionResponse(PermissionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
