from typing import TypeVar, Generic, Type, Any
from math import ceil
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ColumnProperty

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


def _orm_to_dict(obj):
    """将 SQLAlchemy ORM 对象转为字典"""
    if obj is None:
        return None
    result = {}
    mapper = inspect(type(obj))
    for attr in mapper.mapper.column_attrs:
        result[attr.key] = getattr(obj, attr.key)
    return result


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

    def model_dump(self, **kwargs):
        """重写 model_dump，将 SQLAlchemy 对象转为字典"""
        converted_items = []
        for item in self.items:
            if isinstance(item, dict):
                converted_items.append(item)
            elif hasattr(item, '__tablename__'):
                converted_items.append(_orm_to_dict(item))
            else:
                converted_items.append(item)

        return {
            "items": converted_items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
        }


async def paginate(
    db: AsyncSession,
    model: Type[Any],
    params: PaginationParams,
    filters: list | None = None,
    options: list | None = None,
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
    if options:
        stmt = stmt.options(*options).execution_options(populate_existing=True)
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
