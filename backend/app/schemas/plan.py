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
    # 结果推送：绑定的企业微信群机器人 id 列表（空/缺省表示不推送）
    robot_ids: list[int] | None = Field(None, description="绑定的企业微信群机器人 id 列表")


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    """计划更新：所属项目不可变更"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    status: str | None = None
    robot_ids: list[int] | None = Field(None, description="绑定的企业微信群机器人 id 列表")


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
    # 绑定的机器人（编辑回显 + 名称展示）
    robot_ids: list[int] | None = None
    robots: list[dict] = Field(default_factory=list)
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


class CaseExecutionLogResponse(BaseModel):
    """用例执行日志（每次执行一条，保留历史）"""
    id: int
    plan_id: int
    plan_testcase_id: int
    result: str | None = None
    log_content: str | None = None
    tester_id: int | None = None
    tester_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    is_latest: bool = False


# ==================== 定时执行 ====================
ALLOWED_SCHEDULE_MODES = ["full", "custom"]


class PlanScheduleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    cron_expr: str = Field(..., max_length=50, description="cron 表达式（5/6 段）")
    mode: str = Field("full", description="full=全量 / custom=指定用例子集")
    case_ids: list[int] | None = Field(None, description="mode=custom 时的计划内用例 id 列表")
    description: str | None = Field(None, max_length=500, description="说明")


class PlanScheduleCreate(PlanScheduleBase):
    pass


class PlanScheduleUpdate(BaseModel):
    """编辑定时任务（全字段可选，仅更新传入字段）"""
    name: str | None = Field(None, min_length=1, max_length=100)
    cron_expr: str | None = Field(None, max_length=50)
    mode: str | None = None
    case_ids: list[int] | None = None
    description: str | None = Field(None, max_length=500)


class PlanScheduleResponse(BaseModel):
    id: int
    plan_id: int
    created_by: int | None = None
    name: str
    cron_expr: str
    mode: str
    case_ids: list[int] | None = None
    enabled: bool = True
    description: str | None = None
    is_running: bool = False
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_skip_reason: str | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
