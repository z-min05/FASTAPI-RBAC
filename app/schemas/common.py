from pydantic import BaseModel, Field


class IDListRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1)


class PageRequest(BaseModel):
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")
