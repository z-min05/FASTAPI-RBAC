from typing import TypeVar, Generic, Type, Any
from math import ceil
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PaginationParams:
    """分页查询参数依赖"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


async def paginate(
    db: AsyncSession,
    model: Type[Any],
    params: PaginationParams,
    filters: list | None = None,
) -> PaginatedResponse:
    """通用分页查询"""
    # 计算总数
    count_stmt = select(func.count()).select_from(model)
    if filters:
        for f in filters:
            count_stmt = count_stmt.where(f)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 查询数据
    stmt = select(model)
    if filters:
        for f in filters:
            stmt = stmt.where(f)
    stmt = stmt.offset(params.offset).limit(params.page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if total > 0 else 0,
    )
