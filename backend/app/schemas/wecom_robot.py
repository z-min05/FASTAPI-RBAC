from pydantic import BaseModel, Field


class WecomRobotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="机器人名称")
    webhook_url: str = Field(..., min_length=1, max_length=500, description="群机器人 webhook")
    secret: str | None = Field(None, max_length=255, description="加签密钥（可选）")
    description: str | None = Field(None, max_length=500)


class WecomRobotUpdate(BaseModel):
    """编辑机器人；secret 为空表示不修改"""
    name: str | None = Field(None, min_length=1, max_length=100)
    webhook_url: str | None = Field(None, min_length=1, max_length=500)
    secret: str | None = Field(None, max_length=255, description="留空不修改，已加密保存")
    enabled: bool | None = Field(None, description="是否启用")
    description: str | None = Field(None, max_length=500)
