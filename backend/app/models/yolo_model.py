from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class YoloModel(BaseModel):
    """YOLO模型"""
    __tablename__ = "yolo_models"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模型名称")
    version: Mapped[str] = mapped_column(String(50), nullable=False, comment="模型版本如yolov8n")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="模型文件路径(.pt)")
    classes: Mapped[str] = mapped_column(Text, nullable=False, comment="可识别类别JSON数组")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
