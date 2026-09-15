from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PythonEnv(BaseModel):
    """Python 虚拟环境（Miniconda）

    - 环境一律以 `conda create -p <path>`（prefix 模式）创建，路径由
      CONDA_ENV_ROOT + name 推导并在创建时落库；删除与同步都以库中路径为准
    - name 即目录名，创建后不可修改；需要改名/换版本只能删除后重建
    - status 状态机：pending / creating / ready / failed / syncing / lost / deleting
    """
    __tablename__ = "python_envs"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="环境名（同时作为目录名，创建后不可改）"
    )
    python_version: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Python 版本，如 3.11"
    )
    env_path: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False, comment="环境根路径"
    )
    python_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="解释器绝对路径"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True, comment="状态"
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    last_output: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最近一次 conda 命令输出摘要"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次与磁盘同步校验时间"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
