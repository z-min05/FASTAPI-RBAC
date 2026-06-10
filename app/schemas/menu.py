from datetime import datetime
from pydantic import BaseModel, Field


class MenuBriefResponse(BaseModel):
    id: int
    name: str
    path: str | None = None

    model_config = {"from_attributes": True}


class MenuBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    menu_type: str = Field(..., description="类型: directory/menu/button")
    parent_id: int | None = None
    sort: int = 0
    visible: bool = True
    permission: str | None = None


class MenuCreate(MenuBase):
    pass


class MenuUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    menu_type: str | None = None
    parent_id: int | None = None
    sort: int | None = None
    visible: bool | None = None
    permission: str | None = None


class MenuResponse(MenuBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MenuTreeResponse(MenuResponse):
    children: list["MenuTreeResponse"] = []

    model_config = {"from_attributes": True}
