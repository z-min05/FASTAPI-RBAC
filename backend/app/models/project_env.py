from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProjectEnv(BaseModel):
    """自动化测试环境（元信息表）

    只存平台侧补充信息（备注、创建人），**不存环境内容**：
    内容以项目目录下的文件为权威 —— 生效环境 {项目根}/.env、
    环境快照 {项目根}/.envs/<name>.env。
    """
    __tablename__ = "project_envs"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uk_project_envs_project_name"),
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
