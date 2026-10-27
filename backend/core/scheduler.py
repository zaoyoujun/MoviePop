"""轻量后台任务调度器。
基于 threading.Timer + daemon 线程，不依赖外部库。
在 app.py startup 中调用 start_scheduler() 挂载。
"""
from __future__ import annotations

import threading
import time
import logging
from datetime import datetime, timedelta

try:
    from backend.core import jobs_state, tmdb_fetcher, bangumi_fetcher
    from backend.services import db_service
    from backend.config import AppConfig
except ImportError:
    from core import jobs_state, tmdb_fetcher, bangumi_fetcher
    from services import db_service
    from config import AppConfig

logger = logging.getLogger(__name__)

_timer: threading.Timer | None = None
_running = False

# (任务名, 计划时刻 hour:minute, 执行函数)
_DAILY_JOBS = [
    (tmdb_fetcher.TASK_TRENDING, (4, 0), tmdb_fetcher.refresh_trending),
    (tmdb_fetcher.TASK_HOTNESS, (5, 0), tmdb_fetcher.refresh_hotness),
    (tmdb_fetcher.TASK_DETAIL_PREFETCH, (6, 0), tmdb_fetcher.prefetch_details),
]

# (任务名, weekday 0=周一..6=周日, 计划时刻 hour:minute, 执行函数)
_WEEKLY_JOBS = [
    (bangumi_fetcher.TASK_BANGUMI_SYNC, 6, (3, 30), bangumi_fetcher.refresh_bangumi_hotness),
]
_STATE_PREFIX = "scheduler_last_ok:"


def _run_in_thread(name: str, func, *args):
    """在 daemon 线程中执行任务，避免阻塞。"""
    if jobs_state.is_running(name):
        return
    t = threading.Thread(target=func, args=args, daemon=True, name=f"job-{name}")
    t.start()
    return t


def _tracked_run(name: str, func):
    """调度触发的任务：执行完成且无错误时，持久化当天日期，供重启后错过补跑判断。

    手动从页面触发的任务不经过此包装（重复触发幂等，无害）。
    """
    def _runner():
        try:
            func()
        except Exception as exc:
            logger.exception("调度任务 %s 异常: %s", name, exc)
            return
        state = jobs_state.get(name)
        if state.get("done") and not state.get("error"):
            try:
                db_service.set_app_state(_STATE_PREFIX + name, datetime.now().strftime("%Y-%m-%d"))
            except Exception as exc:
                logger.debug("写入调度状态失败: %s", exc)

    if jobs_state.is_running(name) or jobs_state.is_running(tmdb_fetcher.TASK_INITIAL):
        return
    t = threading.Thread(target=_runner, daemon=True, name=f"job-{name}")
    t.start()
    return t


def _last_due_date(scheduled_hour: int, scheduled_minute: int, now: datetime,
                   weekday: int | None = None) -> datetime.date:
    """最近一个应执行日期：今天计划时刻已过则是今天，否则是昨天。

    weekly（weekday 0=周一..6=周日）：最近一个已过去的计划日；若今天是计划日
    但时刻未到，则回溯到上一个计划日。
    """
    due_today = now.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)
    if weekday is None:
        if now >= due_today:
            return now.date()
        return (now - timedelta(days=1)).date()
    days_since = (now.weekday() - weekday) % 7
    due = (now - timedelta(days=days_since)).date()
    if days_since == 0 and now < due_today:
        due -= timedelta(days=7)
    return due


def _catch_up_missed():
    """启动时检查每日/每周任务是否错过（关机跨过计划时刻的场景），错过立即补跑一次。"""
    now = datetime.now()
    for name, (hour, minute), func in _DAILY_JOBS:
        try:
            last_ok = db_service.get_app_state(_STATE_PREFIX + name)
            due = _last_due_date(hour, minute, now)
            if last_ok == due.isoformat():
                continue
            # 片库为空时 fetcher 自身会以 pool_empty 结束；这里不额外拦截，由任务内部处理
            logger.info("检测到任务 %s 错过计划（最近到期 %s，上次成功 %s），启动补跑",
                        name, due.isoformat(), last_ok or "从未")
            _tracked_run(name, func)
        except Exception as exc:
            logger.debug("补跑检查失败 %s: %s", name, exc)
    for name, weekday, (hour, minute), func in _WEEKLY_JOBS:
        try:
            last_ok = db_service.get_app_state(_STATE_PREFIX + name)
            due = _last_due_date(hour, minute, now, weekday=weekday)
            if last_ok == due.isoformat():
                continue
            logger.info("检测到周任务 %s 错过计划（最近到期 %s，上次成功 %s），启动补跑",
                        name, due.isoformat(), last_ok or "从未")
            _tracked_run(name, func)
        except Exception as exc:
            logger.debug("补跑检查失败 %s: %s", name, exc)


def _daily_loop():
    """每分钟检查一次，到点触发对应任务。"""
    global _running
    _running = True
    while _running:
        now = datetime.now()
        # 到点触发（首次下载未完成/任务已在跑则跳过；错过由启动补跑与下一分钟检查兜底）
        for name, (hour, minute), func in _DAILY_JOBS:
            if now.hour == hour and now.minute == minute:
                _tracked_run(name, func)
        for name, weekday, (hour, minute), func in _WEEKLY_JOBS:
            if now.weekday() == weekday and now.hour == hour and now.minute == minute:
                _tracked_run(name, func)
        # 每 60 秒检查一次
        for _ in range(60):
            if not _running:
                return
            time.sleep(1)


def _ensure_initial():
    """启动时若虚拟片库为空且配置了 TMDB key，自动触发首次下载。"""
    config = AppConfig()
    config.load_config()
    if not config.TMDB_API_KEY:
        return
    if not db_service.pool_is_empty():
        return
    if jobs_state.is_running(tmdb_fetcher.TASK_INITIAL):
        return
    _run_in_thread(tmdb_fetcher.TASK_INITIAL, tmdb_fetcher.fetch_initial_pool)


def start_scheduler():
    """在 app startup 中调用，启动每日调度循环 + 首次下载检查 + 错过补跑。"""
    global _timer
    if _timer is not None:
        return
    _ensure_initial()
    _catch_up_missed()
    t = threading.Thread(target=_daily_loop, daemon=True, name="scheduler-loop")
    t.start()
    _timer = t  # 保存引用避免被 GC


def stop_scheduler():
    global _running, _timer
    _running = False
    _timer = None
