from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Camera(BaseModel):
    """ONVIF摄像头模型"""
    __tablename__ = "cameras"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="摄像头名称")
    ip: Mapped[str] = mapped_column(String(50), nullable=False, comment="IP地址")
    port: Mapped[int] = mapped_column(Integer, default=80, nullable=False, comment="ONVIF端口")
    username: Mapped[str] = mapped_column(String(50), nullable=False, comment="ONVIF用户名")
    password: Mapped[str] = mapped_column(String(100), nullable=False, comment="ONVIF密码")
    rtsp_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="RTSP流地址")
    snapshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="抓图URL")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="安装位置")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否在线")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
