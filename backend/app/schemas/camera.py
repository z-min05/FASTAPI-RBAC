from datetime import datetime
from pydantic import BaseModel, Field


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="摄像头名称")
    ip: str = Field(..., min_length=1, max_length=50, description="IP地址")
    port: int = Field(default=80, ge=1, le=65535, description="ONVIF端口")
    username: str = Field(default="admin", min_length=1, max_length=50, description="ONVIF用户名")
    password: str = Field(..., min_length=1, max_length=100, description="ONVIF密码")
    rtsp_url: str | None = Field(None, max_length=500, description="RTSP流地址")
    snapshot_url: str | None = Field(None, max_length=500, description="抓图URL")
    location: str | None = Field(None, max_length=200, description="安装位置")
    description: str | None = Field(None, description="描述")


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    ip: str | None = Field(None, min_length=1, max_length=50)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=1, max_length=100)
    rtsp_url: str | None = Field(None, max_length=500)
    snapshot_url: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class CameraResponse(CameraBase):
    id: int
    is_online: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class CameraBriefResponse(BaseModel):
    id: int
    name: str
    ip: str
    is_online: bool
    model_config = {"from_attributes": True}


class PTZCommand(BaseModel):
    """云台控制命令"""
    pan: float = Field(0.0, ge=-1.0, le=1.0, description="水平方向 -1左 0停 1右")
    tilt: float = Field(0.0, ge=-1.0, le=1.0, description="垂直方向 -1下 0停 1上")
    zoom: float = Field(0.0, ge=-1.0, le=1.0, description="变焦 -1缩小 0停 1放大")


class PTZPreset(BaseModel):
    """预置位"""
    preset_token: str = Field(..., description="预置位token")
    name: str | None = Field(None, description="预置位名称")
