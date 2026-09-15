"""自动化用例异步执行服务

通过 subprocess 调用 pytest 执行单个用例函数，异步完成后更新数据库：
- 子进程注入 PLATFORM_EXEC=1，自动化框架的 loguru 只向 stdout 输出（不再写日志文件）
- 平台逐行接收 stdout 作为该用例完整日志
- plan_testcases.result_desc 保存最新一次执行的完整日志；case_execution_logs 保留全部历史
"""
import asyncio
import os
import re
import subprocess
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# 存储后台任务引用，避免被 GC 回收
_running_tasks: set = set()

# 批量执行停止标志 {plan_id: True=停止}
_stop_batch_flags: dict[int, bool] = {}

# 日志上限，防止超大日志撑爆数据库
_MAX_LOG_CHARS = 500_000


def _strip_ansi(text: str) -> str:
    """去掉 ANSI 颜色控制字符（兜底，框架在管道模式下已无颜色）"""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---------- pytest 结果解析 ----------

def _parse_pytest_result(stdout: str, stderr: str, returncode: int) -> tuple[str, str]:
    """解析 pytest 输出，返回 (result: pass/fail, summary: str)"""
    text = stdout + "\n" + stderr
    failed = len(re.findall(r"(\d+) failed", text))
    errors = len(re.findall(r"(\d+) error", text))
    passed = len(re.findall(r"(\d+) passed", text))

    lines = [l for l in text.splitlines() if l.strip()]
    last_line = lines[-1] if lines else ""

    if failed > 0 or errors > 0 or returncode not in (0, 5):
        reason = _pick_fail_reason(text)
        return "fail", reason or "执行失败"
    elif passed > 0:
        return "pass", last_line or "PASSED"
    elif "no tests ran" in text.lower() or returncode == 5:
        # 函数不存在/被跳过：视为失败，便于定位
        return "fail", "未找到可执行的用例（no tests ran）"
    else:
        return "fail", "NO_RESULT_MATCHED " + (last_line or "")


def _pick_fail_reason(text: str) -> str:
    """从输出中挑一条最能说明失败原因的行（短摘要用）"""
    lines = text.splitlines()
    # 优先 AssertionError 的报错行
    for line in lines:
        s = line.strip()
        if "AssertionError" in s and s.startswith("E ") is False:
            return _trim(s, 200)
    for line in lines:
        s = line.strip()
        if "AssertionError" in s or s.startswith("E "):
            return _trim(s, 200)
    for line in lines:
        s = line.strip()
        if re.search(r"(Error|Exception|TimeoutError)", s):
            return _trim(s, 200)
    return ""


def _trim(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "..."


# ---------- 执行 ----------

async def _run_pytest_async(
    python_path: str,
    test_file: str,
    test_func: str,
    cwd: str,
    timeout: int | None = None,
) -> tuple[str, str, str]:
    """异步执行 pytest 单个函数，返回 (result, summary, full_log)

    timeout 为空时取全局配置 EXEC_TIMEOUT_SECONDS（默认 120 秒）。
    """
    if timeout is None:
        timeout = settings.EXEC_TIMEOUT_SECONDS
    started = datetime.now()
    cmd = [
        python_path,
        "-m", "pytest",
        f"{test_file}::{test_func}",
        "-v",
        "--no-header",
        "-q",
        "--tb=short",
        "-s",  # 关闭 pytest 捕获，让框架 loguru stdout sink 直出
    ]
    env = os.environ.copy()
    env["PLATFORM_EXEC"] = "1"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        msg = f"Python 解释器路径不存在: {python_path}"
        return "fail", msg, msg
    except Exception as e:
        msg = f"EXEC_ERROR: {str(e)}"
        return "fail", msg, msg

    timed_out = False
    try:
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        timed_out = True
        proc.kill()
        try:
            raw, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        except Exception:
            raw = b""

    text = _strip_ansi(raw.decode("utf-8", errors="replace"))
    elapsed = (datetime.now() - started).total_seconds()

    if timed_out:
        result, summary = "fail", f"执行超时（>{timeout} 秒），已强制终止"
    else:
        result, summary = _parse_pytest_result(text, "", proc.returncode)
        if result == "pass" and not re.match(r"^\d+ passed", summary):
            summary = f"通过 · {_trim(summary, 120)}"
        else:
            summary = f"{'通过' if result == 'pass' else '失败'} · {_trim(summary, 200)}"
        summary += f" · 耗时 {elapsed:.1f}s"

    # 限制入库日志长度，超出部分截断并标注
    log_text = text
    if len(log_text) > _MAX_LOG_CHARS:
        log_text = log_text[-_MAX_LOG_CHARS:]
        log_text = "[日志过长已截断(仅保留尾部)]\n" + log_text

    return result, summary, (log_text or f"（无输出）{summary}")


async def _save_execution_result(
    db_session_factory,
    plan_id: int,
    ptc_id: int,
    tester_id: int | None,
    result: str,
    summary: str,
    log_text: str,
    run_token: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    """更新计划用例结果为完整执行日志，并同样写入 case_execution_logs（保留历史）"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.plan_testcase import PlanTestCase
    from app.models.case_execution_log import CaseExecutionLog

    async with db_session_factory() as session:
        session: AsyncSession
        pt = await session.get(PlanTestCase, ptc_id)
        if not pt or pt.plan_id != plan_id:
            return
        pt.result = result
        # 结果记录永远保存最新一次执行的完整日志（不再存简化摘要）
        pt.result_desc = log_text
        if tester_id:
            pt.tester_id = tester_id
        session.add(CaseExecutionLog(
            plan_id=plan_id,
            plan_testcase_id=ptc_id,
            run_token=run_token,
            result=result,
            log_content=log_text,
            tester_id=tester_id,
            started_at=started_at,
            finished_at=finished_at,
        ))
        await session.commit()


async def execute_testcase_background(
    db_session_factory,
    plan_id: int,
    ptc_id: int,
    python_path: str,
    test_file: str,
    test_func: str,
    cwd: str,
    tester_id: int | None,
) -> None:
    """后台执行单个用例，完成后更新结果摘要并把完整日志入库"""
    run_token = uuid.uuid4().hex
    started_at = datetime.now()
    result, summary, log_text = await _run_pytest_async(
        python_path, test_file, test_func, cwd
    )
    await _save_execution_result(
        db_session_factory,
        plan_id,
        ptc_id,
        tester_id,
        result,
        summary,
        log_text,
        run_token,
        started_at,
        datetime.now(),
    )


async def _execute_cases_sequential(
    db_session_factory,
    plan_id: int,
    entries: list[tuple[int, int, str, str]],
    python_path: str,
    cwd: str,
    current_tester_id: int | None,
) -> None:
    """批量串行执行多个用例：执行一条 -> 结果摘要 + 完整日志即刻落库一条"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.plan_testcase import PlanTestCase

    for idx, (ptc_id, _, test_file, test_func) in enumerate(entries):
        # 检查是否被要求停止
        if _stop_batch_flags.get(plan_id):
            _stop_batch_flags.pop(plan_id, None)
            # 剩余未执行的标记为 skipped
            remaining = entries[idx:]
            async with db_session_factory() as session:
                session: AsyncSession
                for rid, _, _, _ in remaining:
                    pt = await session.get(PlanTestCase, rid)
                    if pt and pt.plan_id == plan_id and pt.result == "running":
                        pt.result = "skipped"
                        pt.result_desc = "已被用户终止执行"
                await session.commit()
            return

        # 更新数据库标记为执行中
        async with db_session_factory() as session:
            session: AsyncSession
            pt = await session.get(PlanTestCase, ptc_id)
            if pt and pt.plan_id == plan_id and pt.result == "running":
                pt.result_desc = "正在执行中..."
                if current_tester_id:
                    pt.tester_id = current_tester_id
                await session.commit()

        # 执行单个并落库（一条指令 -> 一条结果 + 一条日志）
        run_token = uuid.uuid4().hex
        started_at = datetime.now()
        result, summary, log_text = await _run_pytest_async(
            python_path, test_file, test_func, cwd
        )
        await _save_execution_result(
            db_session_factory,
            plan_id,
            ptc_id,
            current_tester_id,
            result,
            summary,
            log_text,
            run_token,
            started_at,
            datetime.now(),
        )
