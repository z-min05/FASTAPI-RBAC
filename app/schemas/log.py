from datetime import datetime
from pydantic import BaseModel


class OperationLogResponse(BaseModel):
    id: int
    user_id: int | None
    username: str | None
    method: str
    path: str
    params: str | None
    status_code: int | None
    ip: str | None
    user_agent: str | None
    duration: int | None
    message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
