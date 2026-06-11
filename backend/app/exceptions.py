from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.response import Response


class AppException(HTTPException):
    def __init__(self, status_code: int, message: str = "服务异常"):
        self.message = message
        super().__init__(status_code=status_code, detail=message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "未授权，请先登录"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, message=message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "权限不足，拒绝访问"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, message=message)


class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, message=message)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, message=message)


class ConflictException(AppException):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, message=message)


async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=Response.error(message=exc.message, code=exc.status_code).model_dump(),
    )


async def validation_exception_handler(request, exc: RequestValidationError):
    errors = exc.errors()
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=Response.error(message=detail, code=422).model_dump(),
    )
