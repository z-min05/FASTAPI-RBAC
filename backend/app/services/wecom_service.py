"""企业微信群机器人：CRUD、webhook 发送与测试结果通知组装

- 发送走 httpx（异步），失败仅记录日志，不阻塞/不重试（用"发送测试消息"验证配置）
- webhook_url 含敏感 key 参数，对外一律脱敏；secret 使用 Fernet 加密存储
"""
import asyncio
import base64
import hashlib
import hmac
import time
import urllib.parse
from datetime import datetime
from math import ceil

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto_util import encrypt, decrypt
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import BadRequestException, NotFoundException
from app.models.wecom_robot import WecomRobot
from app.models.plan import TestPlan
from app.models.project import Project
from app.models.plan_testcase import PlanTestCase
from app.models.testcase import TestCase
from app.models.user import User
from app.utils.logger import logger

# 企业微信群机器人 text 单条上限（官方 2048 字节）
MAX_TEXT_BYTES = 2048
# 企业微信群机器人 markdown 单条上限（保守取整）
MAX_MESSAGE_BYTES = 4000
# 限频：每分钟 ≤ 20 条 → 条间最小间隔（秒）
RATE_LIMIT_INTERVAL = 3.0
# 失败/阻塞明细最多列出条数
MAX_FAILURE_ITEMS = 10
# 标题/描述截断长度
_TITLE_CUT = 40
_DESC_CUT = 60


def mask_webhook(url: str | None) -> str:
    """脱敏 webhook：隐藏 key 参数值，仅保留后 4 位"""
    if not url:
        return "-"
    try:
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query))
        key = query.get("key")
        if key:
            query["key"] = ("****" + key[-4:]) if len(key) > 4 else "****"
            return urllib.parse.urlunsplit(
                (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment)
            )
        return f"{parts.scheme}://{parts.netloc}{parts.path}?****"
    except Exception:
        return "****"


def _validate_webhook(url: str) -> None:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise BadRequestException("webhook 必须是 http(s) 地址")
    if "key=" not in url:
        raise BadRequestException("webhook 缺少 key 参数（格式：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx）")


def _sign(timestamp: str, secret: str) -> str:
    """企业微信机器人加签：HMAC-SHA256(timestamp\\nsecret) 后 base64 + urlencode"""
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    return urllib.parse.quote_plus(base64.b64encode(digest))


async def send_markdown(webhook_url: str, secret: str | None, content: str) -> tuple[bool, str]:
    """发送 markdown 消息到企业微信群机器人，返回 (是否成功, 错误信息/ok)"""
    url = webhook_url
    if secret:
        ts = str(int(time.time()))
        sep = "&" if "?" in webhook_url else "?"
        url = f"{webhook_url}{sep}timestamp={ts}&sign={_sign(ts, secret)}"
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        data = resp.json()
    except Exception as e:  # 网络/解析异常均视为失败，仅记录
        return False, f"请求异常: {e}"
    if data.get("errcode") != 0:
        return False, f"企业微信错误 {data.get('errcode')}: {data.get('errmsg')}"
    return True, "ok"


async def send_text(webhook_url: str, secret: str | None, content: str) -> tuple[bool, str]:
    """发送 text 消息到企业微信群机器人（单条 ≤ 2048 字节），返回 (是否成功, 错误/ok)"""
    url = webhook_url
    if secret:
        ts = str(int(time.time()))
        sep = "&" if "?" in webhook_url else "?"
        url = f"{webhook_url}{sep}timestamp={ts}&sign={_sign(ts, secret)}"
    safe = _truncate_bytes(content, MAX_TEXT_BYTES)
    payload = {"msgtype": "text", "text": {"content": safe}}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        data = resp.json()
    except Exception as e:
        return False, f"请求异常: {e}"
    if data.get("errcode") != 0:
        return False, f"企业微信错误 {data.get('errcode')}: {data.get('errmsg')}"
    return True, "ok"


def _split_long_line(line: str, max_bytes: int) -> list[str]:
    """字节安全切分超长单行：不拆断 UTF-8 多字节字符，返回多段"""
    pieces = []
    raw = line.encode("utf-8")
    start, n = 0, len(raw)
    while start < n:
        end = min(start + max_bytes, n)
        while end > start:
            try:
                raw[start:end].decode("utf-8")
                break
            except UnicodeDecodeError:
                end -= 1
        pieces.append(raw[start:end].decode("utf-8"))
        start = end
    return pieces


def _split_by_bytes(text: str, max_bytes: int) -> list[str]:
    """按 max_bytes 字节上限把 text 切为多条，尽量在换行处断开；内容完整保留"""
    chunks: list[str] = []
    buf = ""
    for line in text.split("\n"):
        if len(line.encode("utf-8")) <= max_bytes:
            candidate = f"{buf}\n{line}" if buf else line
            if len(candidate.encode("utf-8")) <= max_bytes:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf)
                buf = line
        else:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_long_line(line, max_bytes))
    if buf:
        chunks.append(buf)
    return chunks


async def send_multipart_text(
    webhook_url: str, secret: str | None, content: str
) -> tuple[int, list[str]]:
    """把 AI 汇总文本分片（≤2048 字节/条）发送，并遵守每分钟 ≤ 20 条限频。

    返回 (成功条数, 错误列表)。分片内容完整保留，不做丢弃。
    """
    parts = _split_by_bytes(content, MAX_TEXT_BYTES)
    ok_count = 0
    errors: list[str] = []
    for i, part in enumerate(parts):
        ok, err = await send_text(webhook_url, secret, part)
        if ok:
            ok_count += 1
        else:
            errors.append(err)
        if i < len(parts) - 1:
            await asyncio.sleep(RATE_LIMIT_INTERVAL)
    return ok_count, errors


def _truncate_bytes(text: str, max_bytes: int = MAX_MESSAGE_BYTES) -> str:
    """按字节截断（企业微信按字节计数，中文需防截断损坏）"""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    return raw[:max_bytes].decode("utf-8", errors="ignore")


def _user_label(u: User | None) -> str:
    if not u:
        return "-"
    return u.nickname or u.username


def _build_notify_message(
    *,
    plan_name: str,
    project_name: str,
    trigger_label: str,
    operator: str,
    started_at: datetime,
    finished_at: datetime,
    total: int,
    passed: int,
    failed: int,
    blocked: int,
    skipped: int,
    interrupted: int,
    failures: list[tuple[str, str, str]],  # (result 标签, 标题, 描述)
    plan_id: int,
) -> str:
    seconds = max(0, int((finished_at - started_at).total_seconds()))
    duration = f"{seconds // 60} 分 {seconds % 60} 秒"
    fmt = "%Y-%m-%d %H:%M:%S"
    denom = passed + failed + blocked
    rate = f"{passed / denom * 100:.2f}%" if denom else "-"

    lines = [
        f"**测试结果通知**",
        "",
        f"测试计划：{plan_name}",
        f"所属项目：{project_name}",
        f"触发方式：{trigger_label}",
        f"发起人：{operator}",
        f"执行时间：{started_at.strftime(fmt)} ~ {finished_at.strftime(fmt)}（耗时 {duration}）",
        "",
        f"**执行统计**（用例 {total} 条）",
        f"通过：<font color=\"info\">{passed}</font>",
        f"失败：<font color=\"warning\">{failed}</font>",
        f"阻塞：<font color=\"warning\">{blocked}</font>",
        f"跳过：{skipped} ｜ 中断：{interrupted}",
        f"**通过率：{rate}**",
    ]
    if failures:
        lines.append("")
        lines.append("失败/阻塞明细：")
        for i, (label, title, desc) in enumerate(failures, start=1):
            if desc:
                lines.append(f"{i}. [{label}] {title} —— {desc}")
            else:
                lines.append(f"{i}. [{label}] {title}")
    base_url = (settings.NOTIFY_FRONTEND_URL or "").rstrip("/")
    if base_url:
        lines.append("")
        lines.append(f"查看完整报告：{base_url}/test/plans/{plan_id}")

    return _truncate_bytes("\n".join(lines))


def _to_response(r: WecomRobot) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "masked_webhook": mask_webhook(r.webhook_url),
        "has_secret": bool(r.secret),
        "enabled": r.enabled,
        "description": r.description,
        "created_by": r.created_by,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


class WecomRobotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, robot_id: int) -> WecomRobot:
        robot = await self.db.get(WecomRobot, robot_id)
        if not robot:
            raise NotFoundException("企业微信群机器人不存在")
        return robot

    async def paginate(
        self, params: PaginationParams, keyword: str | None, enabled: bool | None
    ) -> PaginatedResponse:
        filters = []
        if keyword:
            filters.append(WecomRobot.name.ilike(f"%{keyword}%"))
        if enabled is not None:
            filters.append(WecomRobot.enabled == enabled)

        count_stmt = select(func.count(WecomRobot.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = select(WecomRobot).order_by(WecomRobot.id.desc())
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.offset(params.offset).limit(params.page_size)
        items = list((await self.db.execute(stmt)).scalars().all())

        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=ceil(total / params.page_size) if total > 0 else 0,
        )

    async def list_options(self) -> list[dict]:
        """计划绑定下拉选项：仅 id/name/enabled，不暴露 webhook"""
        rows = (await self.db.execute(select(WecomRobot).order_by(WecomRobot.id.desc()))).scalars().all()
        return [{"id": r.id, "name": r.name, "enabled": r.enabled} for r in rows]

    async def create(self, data, created_by: int) -> WecomRobot:
        url = data.webhook_url.strip()
        _validate_webhook(url)
        robot = WecomRobot(
            name=data.name.strip(),
            webhook_url=url,
            secret=encrypt(data.secret) if data.secret else None,
            description=data.description,
            enabled=True,
            created_by=created_by,
        )
        self.db.add(robot)
        await self.db.flush()
        await self.db.refresh(robot)
        return robot

    async def update(self, robot_id: int, data) -> WecomRobot:
        robot = await self.get(robot_id)
        updates = data.model_dump(exclude_unset=True)
        if "webhook_url" in updates and updates["webhook_url"]:
            url = updates["webhook_url"].strip()
            if url:  # 空串视为不修改（webhook 不回显，前端留空=保留原值）
                _validate_webhook(url)
                robot.webhook_url = url
        if "secret" in updates and updates["secret"]:
            robot.secret = encrypt(updates["secret"])
        if "name" in updates and updates["name"] is not None:
            robot.name = updates["name"].strip()
        if "enabled" in updates:
            robot.enabled = updates["enabled"]
        if "description" in updates:
            robot.description = updates["description"]
        await self.db.flush()
        await self.db.refresh(robot)
        return robot

    async def delete(self, robot_id: int) -> None:
        robot = await self.get(robot_id)
        # 删除保护：被计划引用时拒绝
        ref_ids = (
            (await self.db.execute(select(TestPlan.id).where(TestPlan.robot_ids.contains([robot_id]))))
            .scalars()
            .all()
        )
        if ref_ids:
            raise BadRequestException(
                f"该机器人已被 {len(ref_ids)} 个测试计划绑定，请先到对应计划中取消绑定后再删除"
            )
        await self.db.delete(robot)
        await self.db.flush()

    @staticmethod
    async def send_test(robot: WecomRobot) -> tuple[bool, str]:
        """发送一条测试消息，验证 webhook/加签配置"""
        content = (
            "**测试消息**\n"
            f"> 机器人「{robot.name}」配置验证成功\n"
            "> 如果收到本条消息，说明 webhook 与加签均可用。"
        )
        return await send_markdown(robot.webhook_url, decrypt(robot.secret), content)


def _one_line(s: str | None) -> str:
    return " ".join((s or "").strip().split())


def _build_agent_prompt(plan: TestPlan, trigger_label: str, rows: list, stat: dict) -> str:
    """整合本轮已执行用例（标题/预期结果/执行结果/结果描述）为发给 Agent 的 prompt。

    内容全量保留，不做截断；仅把每个字段单行化以便阅读。
    """
    lines = [
        f"测试计划「{plan.name}」本次由“{trigger_label}”触发执行完成，共 {len(rows)} 条用例。",
        f"统计：通过 {stat['pass']}、失败 {stat['fail']}、阻塞 {stat['blocked']}、"
        f"跳过 {stat['skipped']}、中断 {stat['interrupted']}。",
        "请基于下面每条用例的标题、预期结果、实际执行结果与结果描述，归纳测试结论与需要关注的问题。",
        "用例明细：",
    ]
    for i, (pt, tc) in enumerate(rows, start=1):
        title = _one_line(tc.title) if tc else "未知用例"
        lines.append(f"{i}. [结果:{pt.result or 'unset'}] {title}")
        lines.append(f"   预期结果: {_one_line(tc.expected_result) if tc else ''}")
        if pt.result_desc:
            lines.append(f"   结果描述: {_one_line(pt.result_desc)}")
    return "\n".join(lines)


async def _call_agent_summary(db, plan: TestPlan, trigger_label: str, rows: list, stat: dict) -> str | None:
    """非流式调用计划绑定的 Agent 会话获取汇总 reply；失败返回 None（由调用方回退统计）"""
    from app.models.agent_conversation import AgentConversation
    from app.services.agent_service import AgentService

    try:
        conv = await db.get(AgentConversation, plan.agent_conversation_id)
        if not conv:
            logger.info(f"计划 {plan.id} 绑定的汇总会话不存在，回退统计推送")
            return None
        prompt = _build_agent_prompt(plan, trigger_label, rows, stat)
        result = await AgentService(db).send_message(conv.user_id, conv.id, prompt)
        reply = (result.get("reply") or "").strip()
        if not reply:
            logger.warning(f"计划 {plan.id} AI 未返回内容，回退统计推送")
            return None
        return reply
    except Exception as e:
        logger.warning(f"计划 {plan.id} AI 汇总失败，回退统计推送: {e}")
        return None


async def notify_plan_finished(
    plan_id: int,
    trigger_label: str,
    operator_user_id: int | None,
    entries_ptc_ids: list[int],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    """计划整轮执行（批量/定时）结束后，向绑定机器人推送本轮统计。

    旁路通知：读取失败/发送失败均只记录日志，不影响执行主流程。
    """
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            plan = await db.get(TestPlan, plan_id)
            if not plan or not plan.robot_ids:
                logger.info(f"计划 {plan_id} 整轮结束({trigger_label})，未绑定推送机器人，跳过企业微信通知")
                return
            robots = (
                (
                    await db.execute(
                        select(WecomRobot).where(
                            WecomRobot.id.in_(plan.robot_ids),
                            WecomRobot.enabled.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not robots:
                logger.info(f"计划 {plan_id} 绑定的机器人均不存在或已停用，跳过企业微信通知")
                return

            project_name = "-"
            if plan.project_id:
                proj = await db.get(Project, plan.project_id)
                project_name = proj.name if proj else "-"
            operator = _user_label(await db.get(User, operator_user_id)) if operator_user_id else "-"

            # 本轮参与的用例结果（仅取计划内、属于本轮 entries 的行）
            rows = (
                (
                    await db.execute(
                        select(PlanTestCase, TestCase)
                        .join(TestCase, PlanTestCase.testcase_id == TestCase.id)
                        .where(PlanTestCase.id.in_(entries_ptc_ids))
                    )
                )
                .all()
            )
            rows = [(pt, tc) for pt, tc in rows if pt.plan_id == plan_id]
            if not rows:
                return

            stat = {"pass": 0, "fail": 0, "blocked": 0, "skipped": 0, "interrupted": 0}
            failures: list[tuple[str, str, str]] = []
            for pt, tc in rows:
                res = pt.result or ""
                if res == "pass":
                    stat["pass"] += 1
                elif res == "fail":
                    stat["fail"] += 1
                elif res == "blocked":
                    stat["blocked"] += 1
                elif res == "skipped":
                    stat["skipped"] += 1
                else:  # running/未知/异常遗留
                    stat["interrupted"] += 1
                if res in ("fail", "blocked") and len(failures) < MAX_FAILURE_ITEMS:
                    label = "失败" if res == "fail" else "阻塞"
                    title = (tc.title if tc else "未知用例")
                    title = title if len(title) <= _TITLE_CUT else title[:_TITLE_CUT] + "…"
                    desc = (pt.result_desc or "").replace("\n", " ").strip()
                    # 结果记录为完整日志时，取末尾（错误摘要/失败原因通常在最末）更有价值
                    desc = desc if len(desc) <= _DESC_CUT else "…" + desc[-_DESC_CUT:]
                    failures.append((label, title, desc))

            # AI 汇总优先：绑定会话则调用 Agent 拿 reply；失败自动回退统计
            ai_reply: str | None = None
            if plan.agent_conversation_id:
                ai_reply = await _call_agent_summary(db, plan, trigger_label, rows, stat)
                # 本会话未走 get_db 依赖，不会自动提交；必须显式提交，
                # 否则会话关闭时本轮对话消息与 token 记录会被回滚丢弃。
                # 提交失败仅告警，不能影响后续推送。
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.warning(f"计划 {plan_id} 汇总对话落库失败，已回滚", exc_info=True)

            content = None
            if not ai_reply:
                content = _build_notify_message(
                    plan_name=plan.name,
                    project_name=project_name,
                    trigger_label=trigger_label,
                    operator=operator,
                    started_at=started_at,
                    finished_at=finished_at,
                    total=len(rows),
                    passed=stat["pass"],
                    failed=stat["fail"],
                    blocked=stat["blocked"],
                    skipped=stat["skipped"],
                    interrupted=stat["interrupted"],
                    failures=failures,
                    plan_id=plan.id,
                )

        # 逐机器人发送（会话已关闭，发送阶段不再依赖 DB；AI 文本走分片+限频，统计走单条 markdown）
        logger.info(
            f"计划 {plan_id} 企业微信通知发送开始：{len(robots)} 个机器人，"
            f"用例 {len(rows)}（通过 {stat['pass']}/失败 {stat['fail']}/阻塞 {stat['blocked']}/跳过 {stat['skipped']}）"
            + ("" if ai_reply else "，AI 汇总失败/未配置，回退统计")
        )
        for robot in robots:
            secret = decrypt(robot.secret)
            if ai_reply:
                ok_count, errors = await send_multipart_text(robot.webhook_url, secret, ai_reply)
                if not ok_count:
                    logger.error(f"企业微信群机器人「{robot.name}」(id={robot.id}) AI 推送全失败: {errors}")
            else:
                ok, err = await send_markdown(robot.webhook_url, secret, content)
                if not ok:
                    logger.error(f"企业微信群机器人「{robot.name}」(id={robot.id}) 推送失败: {err}")
    except Exception as e:  # 通知属旁路，任何异常不得向上抛出
        logger.error(f"计划 {plan_id} 测试结果通知发送异常: {e}")
