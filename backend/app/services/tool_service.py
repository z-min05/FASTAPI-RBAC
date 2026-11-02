"""工具管理服务

- 每个工具包含「压缩包」与「README 文档」两个文件，均落盘到
  ``settings.tool_storage_root``，数据库只存相对文件名（storage key）。
- 上传使用随机文件名落盘，避免同名覆盖与路径穿越；原始文件名仅用于展示/下载。
- 删除时先删磁盘文件、再删数据库记录；文件删除失败会抛异常回滚记录，
  避免出现「记录没了但文件还在」的静默残留。
"""
import uuid
import zipfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.pagination import PaginationParams
from app.exceptions import BadRequestException, NotFoundException
from app.models.tool import Tool
from app.models.user import User
from app.repositories.base import BaseRepository
from app.utils.logger import logger

# README 文件大小上限（字节）：README 仅用于页面展示，无需支持超大文件
_README_MAX_BYTES = 2 * 1024 * 1024
# README 返回前端的字符上限，超出部分截断并提示
_README_DISPLAY_LIMIT = 200_000
# 写入磁盘的分块大小
_CHUNK_SIZE = 1024 * 1024


def _storage_root() -> Path:
    """存储根目录（不存在时自动创建）"""
    root = Path(settings.tool_storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _package_max_bytes() -> int:
    return max(settings.TOOL_UPLOAD_MAX_MB, 1) * 1024 * 1024


def _check_suffix(upload: UploadFile, suffix: str, label: str) -> None:
    filename = (upload.filename or "").strip()
    if not filename.lower().endswith(suffix):
        raise BadRequestException(f"{label} 仅支持 {suffix} 格式文件")


async def _save_upload(upload: UploadFile, dest: Path, max_bytes: int, label: str) -> int:
    """把上传文件分块写入 dest，超过大小上限时清理并报错"""
    size = 0
    try:
        with dest.open("wb") as f:
            while chunk := await upload.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise BadRequestException(f"{label} 超过大小上限（{max_bytes // 1024 // 1024} MB）")
                f.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return size


def to_response(tool: Tool, created_by_name: str | None = None, readme_content: str | None = None) -> dict:
    data = {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "package_filename": tool.package_filename,
        "package_size": tool.package_size,
        "readme_filename": tool.readme_filename,
        "readme_size": tool.readme_size,
        "created_by": tool.created_by,
        "created_by_name": created_by_name,
        "created_at": tool.created_at,
        "updated_at": tool.updated_at,
    }
    if readme_content is not None:
        data["readme_content"] = readme_content
    return data


class ToolService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BaseRepository(Tool, db)

    # ---------- 查询 ----------

    async def paginate(self, params: PaginationParams, keyword: str | None = None):
        filters = []
        if keyword:
            filters.append(Tool.name.ilike(f"%{keyword}%"))
        return await self.repo.get_paginated(
            params, filters=filters, order_by=[Tool.id.desc()]
        )

    async def get(self, tool_id: int) -> Tool:
        tool = await self.db.get(Tool, tool_id)
        if not tool:
            raise NotFoundException("工具不存在")
        return tool

    async def user_name_map(self, user_ids: set[int | None]) -> dict[int, str]:
        ids = [i for i in user_ids if i]
        if not ids:
            return {}
        stmt = select(User.id, User.nickname, User.username).where(User.id.in_(ids))
        rows = (await self.db.execute(stmt)).all()
        return {r[0]: (r[1] or r[2] or f"#{r[0]}") for r in rows}

    def read_readme(self, tool: Tool) -> str:
        """读取 README 文本内容（UTF-8，非法字节替换），超过展示上限时截断"""
        path = _storage_root() / tool.readme_path
        if not path.is_file():
            return "（README 文件不存在或已被删除）"
        raw = path.read_bytes()
        text = raw[:_README_DISPLAY_LIMIT].decode("utf-8", errors="replace")
        if len(raw) > _README_DISPLAY_LIMIT:
            text += "\n\n...（README 内容过长，仅展示前 200000 字节）"
        return text

    def package_abs_path(self, tool: Tool) -> Path:
        path = _storage_root() / tool.package_path
        if not path.is_file():
            raise NotFoundException("压缩包文件不存在或已被删除")
        return path

    # ---------- 增 / 删 ----------

    async def create(
        self,
        name: str,
        description: str | None,
        package: UploadFile,
        readme: UploadFile,
        user_id: int | None,
    ) -> Tool:
        _check_suffix(package, ".zip", "压缩包")
        _check_suffix(readme, ".md", "README")

        root = _storage_root()
        package_key = f"{uuid.uuid4().hex}.zip"
        readme_key = f"{uuid.uuid4().hex}.md"
        package_path = root / package_key
        readme_path = root / readme_key

        try:
            package_size = await _save_upload(package, package_path, _package_max_bytes(), "压缩包")
            if not zipfile.is_zipfile(package_path):
                raise BadRequestException("上传的文件不是有效的 zip 压缩包")
            readme_size = await _save_upload(readme, readme_path, _README_MAX_BYTES, "README")

            tool = Tool(
                name=name.strip(),
                description=(description or "").strip() or None,
                package_filename=(package.filename or "package.zip").strip(),
                package_path=package_key,
                package_size=package_size,
                readme_filename=(readme.filename or "README.md").strip(),
                readme_path=readme_key,
                readme_size=readme_size,
                created_by=user_id,
            )
            self.db.add(tool)
            await self.db.flush()
            await self.db.refresh(tool)
            return tool
        except Exception:
            # 落盘失败或入库失败：清理已写入的文件，避免磁盘残留
            package_path.unlink(missing_ok=True)
            readme_path.unlink(missing_ok=True)
            raise

    async def delete(self, tool_id: int) -> None:
        tool = await self.get(tool_id)
        root = _storage_root()
        for key in (tool.package_path, tool.readme_path):
            try:
                (root / key).unlink(missing_ok=True)
            except OSError as e:  # 文件被占用等
                logger.warning(f"删除工具文件失败: {root / key}: {e}")
                raise BadRequestException(f"删除文件失败: {e}")
        await self.db.delete(tool)
        await self.db.flush()
