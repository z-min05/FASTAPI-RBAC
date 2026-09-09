"""内嵌调度循环

随 FastAPI 进程（lifespan）启动的后台 asyncio 任务，周期性扫描到期的定时任务并触发。
- 多 worker/多进程下到点任务的"认领"由 schedule_service.trigger_schedule 内 DB 条件更新保证，
  本循环只需每 tick 扫描候选并逐个触发（认领失败的会被条件更新挡住）。
- 僵尸任务（running 超时）在每次 tick 先自动复位。
"""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.plan_schedule import PlanSchedule
from app.services.schedule_service import trigger_schedule
from app.utils.logger import logger


async def _tick() -> None:
    now = datetime.now()
    try:
        async with AsyncSessionLocal() as db:
            # 1. 僵尸复位：标记运行中但超过阈值 -> 异常中断，自动复位
            stale_before = now - timedelta(hours=settings.SCHEDULER_ZOMBIE_TIMEOUT_HOURS)
            await db.execute(
                update(PlanSchedule)
                .where(
                    PlanSchedule.is_running.is_(True),
                    PlanSchedule.running_since.is_not(None),
                    PlanSchedule.running_since < stale_before,
                )
                .values(
                    is_running=False,
                    running_since=None,
                    last_status="error",
                    last_skip_reason="检测到执行异常中断，已自动复位",
                )
            )
            await db.commit()

            # 2. 扫描到期候选（enabled 且未运行且到点）
            rows = (
                (
                    await db.execute(
                        select(PlanSchedule)
                        .where(
                            PlanSchedule.enabled.is_(True),
                            PlanSchedule.is_running.is_(False),
                            PlanSchedule.next_run_at.is_not(None),
                            PlanSchedule.next_run_at <= now,
                        )
                        .order_by(PlanSchedule.id)
                    )
                )
                .scalars()
                .all()
            )
    except Exception as e:
        logger.warning(f"调度 tick 扫描异常: {e}")
        return

    # 3. 逐个触发（认领失败/冲突跳过均在 trigger_schedule 内安全处理）
    for s in rows:
        try:
            await trigger_schedule(s.id)
        except Exception as e:
            logger.warning(f"触发定时任务失败 (schedule={s.id}): {e}")


async def scheduler_loop() -> None:
    logger.info(
        f"定时执行调度器已启动 (tick={settings.SCHEDULER_TICK_SECONDS}s, "
        f"zombie_timeout={settings.SCHEDULER_ZOMBIE_TIMEOUT_HOURS}h)"
    )
    while True:
        try:
            await _tick()
        except Exception as e:
            logger.warning(f"调度循环异常: {e}")
        await asyncio.sleep(settings.SCHEDULER_TICK_SECONDS)
