from typing import Any, Optional
from pydantic import BaseModel


class Response(BaseModel):
    """统一响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success", code: int = 200) -> "Response":
        return cls(code=code, message=message, data=data)

    @classmethod
    def error(cls, message: str = "error", code: int = 500, data: Any = None) -> "Response":
        return cls(code=code, message=message, data=data)
