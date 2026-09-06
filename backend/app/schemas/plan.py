from datetime import datetime
from pydantic import BaseModel, Field

# 计划状态
ALLOWED_PLAN_STATUS = ["not_started", "in_progress", "completed"]
# 计划用例测试结果（running 为执行中状态）
ALLOWED_RESULTS = ["pass", "fail", "blocked", "skipped", "running"]
# 结果统计 key 顺序（pending = 已加入计划但未回填结果）
RESULT_STAT_KEYS = ["pass", "fail", "blocked", "skipped", "pending"]


class PlanBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="计划名称")
    project_id: int = Field(..., description="所属项目 ID")
    description: str | None = Field(None, description="计划说明")
    status: str = Field("not_started", description="计划状态：not_started/in_progress/completed")


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    """计划更新：所属项目不可变更"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    status: str | None = None


class PlanResponse(BaseModel):
    id: int
    project_id: int
    project_code: str | None = None
    project_name: str | None = None
    name: str
    description: str | None = None
    status: str
    case_count: int = 0
    result_stats: dict = Field(default_factory=lambda: {k: 0 for k in RESULT_STAT_KEYS})
    created_at: datetime
    updated_at: datetime


class PlanTestCaseResponse(BaseModel):
    """计划用例：关联行信息 + 用例实时内容（不复制）"""
    id: int
    plan_id: int
    testcase_id: int
    title: str | None = None
    module: str | None = None
    priority: str | None = None
    case_type: str | None = None
    source: str | None = None
    status: str | None = None  # 用例管理状态
    precondition: str | None = None
    steps: str | None = None
    expected_result: str | None = None
    tester_id: int | None = None
    tester_name: str | None = None
    result: str | None = None
    result_desc: str | None = None
    module_code: str | None = None
    case_code: str | None = None
    created_at: datetime
    updated_at: datetime


class PlanTestcaseAddRequest(BaseModel):
    testcase_ids: list[int] = Field(..., min_length=1, description="用例 ID 列表")


class PlanTestcaseResultUpdate(BaseModel):
    """记录/修改测试结果（测试人由后端自动设为当前用户）"""
    result: str | None = None
    result_desc: str | None = None


class TesterOption(BaseModel):
    id: int
    username: str
    nickname: str | None = None
