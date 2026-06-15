from sqlalchemy import String, Integer, Boolean, Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class DetectionTask(BaseModel):
    """识别任务"""
    __tablename__ = "detection_tasks"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="任务名称")
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=False, comment="摄像头ID")
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("yolo_models.id"), nullable=False, comment="YOLO模型ID")
    target_classes: Mapped[str] = mapped_column(Text, nullable=False, comment="目标识别类别JSON数组")
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, comment="置信度阈值")
    interval_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False, comment="识别间隔(秒)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否启用")
    last_run_at: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="上次执行时间")
