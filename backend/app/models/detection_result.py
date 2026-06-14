from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class DetectionResult(BaseModel):
    """识别结果"""
    __tablename__ = "detection_results"

    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("detection_tasks.id"), nullable=False, comment="任务ID")
    image_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="原始图片路径")
    annotated_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="标注图片路径")
    detections: Mapped[str] = mapped_column(Text, nullable=False, comment="识别结果JSON")
    detected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="识别到的目标数")
