"""Bangumi 动漫数据补充（阶段五）。

从 api.bgm.tv（官方 v0 API，免费、无风控）拉取热门动漫 Top N 补充进虚拟片库：
- 条目以 source='bangumi'、media_type='anime'、id='bangumi:{subject_id}' 入库，
  入库即含详情级数据（中文标题/简介/评分/海报），detail_fetched=1，无需懒加载；
- 评分与收藏数同时写入 hotness_series（source='bangumi'），作为动漫热度信号参与趋势分析；
- 每周日 03:30 调度刷新已入库条目的热度快照（1 req/s 礼貌限速）。

注意：Bangumi API 要求自定义 User-Agent，禁用默认 UA；不做 TMDB↔Bangumi 名称模糊匹配
（误配风险高），Bangumi 热度信号仅覆盖其源条目。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import requests

try:
    from backend.core import jobs_state
    from backend.services import db_service
except ImportError:
    from core import jobs_state
    from services import db_service

logger = logging.getLogger(__name__)

BANGUMI_API = "https://api.bgm.tv"
TASK_BANGUMI_SYNC = "bangumi_sync"          # 每周日 03:30：刷新已入库动漫热度

# Bangumi 要求能识别调用方的自定义 UA，禁用库默认 UA（否则 403/418）
_HEADERS = {
    "User-Agent": "jmh-moviepop/1.0 (local media library; personal use)",
    "Accept": "application/json",
}
_REFRESH_INTERVAL = 1.0         # 详情刷新 1 req/s（周任务全量 1000 条约 17 分钟，可接受）


def _api_get_subject(subject_id: str | int) -> dict | None:
    """v0 条目详情：rating/collection/summary。失败返回 None。"""
    try:
        resp = requests.get(
            f"{BANGUMI_API}/v0/subjects/{subject_id}",
            headers=_HEADERS, timeout=(5, 15),
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("Bangumi 条目失败 id=%s error=%s", subject_id, exc)
        return None


def _subject_to_hotness(subject: dict[str, Any], now_iso: str) -> dict[str, Any] | None:
    """Bangumi subject → hotness_series 快照（收藏数 + 评分）。"""
    sid = str(subject.get("id") or "")
    if not sid:
        return None
    rating = subject.get("rating") or {}
    collection = subject.get("collection") or {}
    return {
        "pool_id": f"bangumi:{sid}",
        "source": "bangumi",
        "external_id": sid,
        "vote_average": rating.get("score"),
        "vote_count": rating.get("total"),
        "popularity": None,
        "collection_count": collection.get("collect"),
        "fetched_at": now_iso,
    }


def refresh_bangumi_hotness() -> None:
    """刷新已入库 Bangumi 条目的热度快照（每周日 03:30 调度，可手动触发）。

    逐条 GET /v0/subjects/{id}（1 req/s），失败条目跳过不影响整体。
    注：动漫主体库已改为 TMDB discover 数据源（见 tmdb_fetcher.pull_anime_top），
    本任务仅维护早期经 /api/jobs/bangumi-pull 入库的少量 Bangumi 条目。
    """
    items = db_service.list_pool_ids_by_source("bangumi")
    if not items:
        jobs_state.finish(
            TASK_BANGUMI_SYNC, label="片库暂无 Bangumi 动漫，先执行拉取任务", error="empty")
        return
    jobs_state.start(TASK_BANGUMI_SYNC, label=f"正在刷新 {len(items)} 条动漫热度…")
    snapped = 0
    for idx, row in enumerate(items):
        if jobs_state.is_cancel_requested(TASK_BANGUMI_SYNC):
            jobs_state.finish(
                TASK_BANGUMI_SYNC,
                label=f"已取消（已刷新 {snapped} 条）", error="cancelled")
            return
        subject = _api_get_subject(row.get("external_id") or "")
        if subject:
            snap = _subject_to_hotness(subject, datetime.now().isoformat(timespec="seconds"))
            if snap:
                db_service.insert_hotness_batch([snap])
                snapped += 1
        jobs_state.update(
            TASK_BANGUMI_SYNC, (idx + 1) / len(items),
            f"已刷新 {snapped} / {len(items)} 条")
        time.sleep(_REFRESH_INTERVAL)
    jobs_state.finish(TASK_BANGUMI_SYNC, label=f"完成，共刷新 {snapped} 条热度快照")
