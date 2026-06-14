from datetime import datetime
from pydantic import BaseModel, Field


class DetectionTaskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    camera_id: int = Field(..., description="摄像头ID")
    model_id: int = Field(..., description="YOLO模型ID")
    target_classes: str = Field(..., description="目标识别类别JSON数组")
    interval_seconds: int = Field(default=30, ge=5, le=3600, description="识别间隔(秒)")


class DetectionTaskCreate(DetectionTaskBase):
    pass


class DetectionTaskUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    camera_id: int | None = None
    model_id: int | None = None
    target_classes: str | None = None
    interval_seconds: int | None = Field(None, ge=5, le=3600)
    is_active: bool | None = None


class DetectionTaskResponse(DetectionTaskBase):
    id: int
    is_active: bool
    last_run_at: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
