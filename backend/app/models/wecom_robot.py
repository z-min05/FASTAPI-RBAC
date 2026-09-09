from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WecomRobot(BaseModel):
    """企业微信群机器人：推送测试结果通知的目标

    - webhook_url：群机器人 webhook（含 key 参数），泄漏等同可向该群发消息，接口一律脱敏
    - secret：安全设置-加签 密钥，Fernet 加密存放，仅写入不回显
    """
    __tablename__ = "wecom_robots"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="机器人名称")
    webhook_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="群机器人 webhook")
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="加签密钥（加密存储）")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
