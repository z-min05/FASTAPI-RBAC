from datetime import datetime
from pydantic import BaseModel, Field


class YoloModelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="模型名称")
    version: str = Field(..., min_length=1, max_length=50, description="模型版本如yolov8n")
    file_path: str = Field(..., min_length=1, max_length=500, description="模型文件路径(.pt)")
    classes: str = Field(..., description="可识别类别JSON数组")
    description: str | None = Field(None, description="描述")


class YoloModelCreate(YoloModelBase):
    pass


class YoloModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    version: str | None = Field(None, min_length=1, max_length=50)
    file_path: str | None = Field(None, min_length=1, max_length=500)
    classes: str | None = None
    description: str | None = None
    is_active: bool | None = None


class YoloModelResponse(YoloModelBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
