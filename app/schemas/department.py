from datetime import datetime
from pydantic import BaseModel, Field


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    code: str | None = None
    parent_id: int | None = None
    sort: int = 0
    leader: str | None = None
    phone: str | None = None
    status: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    parent_id: int | None = None
    sort: int | None = None
    leader: str | None = None
    phone: str | None = None
    status: bool | None = None


class DepartmentResponse(DepartmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DepartmentTreeResponse(DepartmentResponse):
    children: list["DepartmentTreeResponse"] = []

    model_config = {"from_attributes": True}
