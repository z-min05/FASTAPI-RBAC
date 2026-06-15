from datetime import datetime
from pydantic import BaseModel, Field


class DetectionResultResponse(BaseModel):
    id: int
    task_id: int
    image_path: str
    annotated_image_path: str | None
    detections: str
    detected_count: int
    created_at: datetime
    model_config = {"from_attributes": True}
