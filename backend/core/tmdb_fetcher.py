"""TMDB 精选元数据拉取模块。
从 TMDB API 按 popular/top_rated/trending 分页拉取约 1 万条精选条目，存入 metadata_pool。
5 req/s 限速，失败指数退避重试。
详情懒加载（首次只拉列表基础字段），浏览时按需补全。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import requests

try:
    from backend.config import AppConfig
    from backend.core import jobs_state
    from backend.core import genre_taxonomy
    from backend.services import db_service
except ImportError:
    from config import AppConfig
    from core import jobs_state
    from core import genre_taxonomy
    from services import db_service

logger = logging.getLogger(__name__)

TASK_INITIAL = "pool_initial"  # 首次全量拉取
TASK_TRENDING = "trending_refresh"  # 每日 trending 刷新
TASK_HOTNESS = "hotness_refresh"  # 热度快照
TASK_GENRE_BACKFILL = "genre_backfill"  # 题材回填（重放列表计划补 genre_ids/genres）
TASK_DETAIL_PREFETCH = "detail_prefetch"  # 详情预拉取（每日 06:00 Top 2000）
TASK_ANIME_PULL = "anime_pull"  # TMDB 日本动漫 Top N（手动触发）

# 限速：200ms 一请求 ≈ 5 req/s
_REQUEST_INTERVAL = 0.2
_MAX_RETRIES = 3

# 榜单拉取计划：trending / popular / top_rated（这些榜单彼此重叠度高，
# 去重后约 5~6 千条）。
_CHART_PLAN = [
    {"endpoint": "/trending/movie/week", "pages": 10, "media_type": "movie"},  # 200
    {"endpoint": "/trending/tv/week", "pages": 10, "media_type": "tv"},        # 200
    {"endpoint": "/movie/popular", "pages": 100, "media_type": "movie"},      # 2000
    {"endpoint": "/tv/popular", "pages": 100, "media_type": "tv"},            # 2000
    {"endpoint": "/movie/top_rated", "pages": 75, "media_type": "movie"},     # 1500
    {"endpoint": "/tv/top_rated", "pages": 75, "media_type": "tv"},            # 1500
]

# discover tv 时排除的类型：真人秀 / 脱口秀 / 新闻 / 肥皂剧
# （这些不是典型"影视"，且会污染推荐与榜单）
_TV_EXCLUDE_GENRES = "10764|10767|10763|10766"


def _build_fetch_plan() -> list[dict]:
    """完整拉取计划 = 榜单 + discover 按年份。

    discover 按年份是独立增量主力：不同年份的影片几乎不重叠，
    能把榜单（popular/top_rated/trending 高度重叠）覆盖不到的
    各年代类型片补进来，使去重后总量稳定在约 1 万条。
    """
    plan = list(_CHART_PLAN)
    current_year = datetime.now().year

    # 电影：1985 年至今。榜单（popular/top_rated）已覆盖跨年份最热的头部，
    # 因此这里按年份往深页拉——每年第 3~7 页是当年热门但未进总榜的独立增量。
    # 近年片多，每年 7 页；早年每年 4 页。深页仍要求 vote_count>=50 保证质量。
    for year in range(1985, current_year + 1):
        pages = 7 if year >= 2000 else 4
        plan.append({
            "endpoint": "/discover/movie",
            "media_type": "movie",
            "pages": pages,
            "params": {
                "sort_by": "popularity.desc",
                "vote_count.gte": 50,
                "primary_release_year": year,
            },
        })

    # 剧集：1990 年至今，近年每年 7 页、早年每年 4 页，
    # 深页仍要求 vote_count>=60，排除综艺/脱口秀/新闻/肥皂剧。
    for year in range(1990, current_year + 1):
        pages = 7 if year >= 2005 else 4
        plan.append({
            "endpoint": "/discover/tv",
            "media_type": "tv",
            "pages": pages,
            "params": {
                "sort_by": "popularity.desc",
                "vote_count.gte": 60,
                "first_air_date_year": year,
                "without_genres": _TV_EXCLUDE_GENRES,
            },
        })

    return plan


# 拉取规模配置（榜单 + 按年份发现，合计去重后约 1 万条）
_FETCH_PLAN = _build_fetch_plan()

# 热度快照拉取计划：trending + popular 覆盖当前最热集合（约 1400 条/轮），
# 响应自带 vote_count/popularity/vote_average，无需逐条 detail 请求。
_HOTNESS_PLAN = [
    {"endpoint": "/trending/movie/week", "pages": 10, "media_type": "movie"},
    {"endpoint": "/trending/tv/week", "pages": 10, "media_type": "tv"},
    {"endpoint": "/movie/popular", "pages": 25, "media_type": "movie"},
    {"endpoint": "/tv/popular", "pages": 25, "media_type": "tv"},
]


def _config() -> AppConfig:
    return AppConfig()


def _api_get(api_key: str, api_base: str, endpoint: str, params: dict | None = None) -> dict:
    """TMDB API GET，带限速与重试。"""
    params = dict(params or {})
    params["api_key"] = api_key
    params.setdefault("language", "zh-CN")
    url = f"{api_base.rstrip('/')}{endpoint}"
    last_err = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            time.sleep(_REQUEST_INTERVAL)
            return resp.json()
        except Exception as exc:
            last_err = str(exc)
            # 指数退避
            time.sleep(2 ** attempt * 0.5)
    logger.warning("TMDB 请求失败 endpoint=%s error=%s", endpoint, last_err)
    return {}


def _normalize_item(raw: dict, media_type: str,
                    movie_map: dict[int, str], tv_map: dict[int, str]) -> dict:
    """把 TMDB 列表项归一化为 metadata_pool 行。

    列表接口（discover/popular/trending）返回 genre_ids（id 数组，非 genres 对象），
    用对应 media_type 的题材表映射成中文名；movie/tv 两套 id 体系不可混用。
    """
    external_id = str(raw.get("id") or "")
    release_date = raw.get("release_date") or raw.get("first_air_date") or ""
    year = None
    if release_date and len(release_date) >= 4:
        try:
            year = int(release_date[:4])
        except ValueError:
            year = None
    raw_genre_ids = raw.get("genre_ids") or []
    genre_ids = [int(g) for g in raw_genre_ids if str(g).strip().isdigit()]
    genres = genre_taxonomy.map_genre_ids_to_names(genre_ids, media_type, movie_map, tv_map)
    return {
        "id": f"tmdb:{external_id}",
        "source": "tmdb",
        "external_id": external_id,
        "media_type": media_type,
        "title": raw.get("title") or raw.get("name") or "",
        "original_title": raw.get("original_title") or raw.get("original_name") or "",
        "release_date": release_date,
        "year": year,
        "overview": raw.get("overview") or "",
        "genres": genres,  # 列表项 genre_ids 映射；详情懒加载再补全
        "genre_ids": genre_ids,
        "poster_path": raw.get("poster_path") or "",
        "backdrop_path": raw.get("backdrop_path") or "",
        "vote_average": raw.get("vote_average"),
        "vote_count": raw.get("vote_count"),
        "popularity": raw.get("popularity"),
        "origin_country": raw.get("origin_country") or [],
        "runtime": None,
        "status": "",
        "detail_fetched": 0,
        "fetched_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def ensure_genre_maps(api_key: str, api_base: str, force: bool = False) -> tuple[dict, dict]:
    """确保 movie/tv 两张题材映射表可用，返回 (movie_map, tv_map)。

    优先读库；缺失或 force 时联网：zh-CN 取名（TV 部分类型 TMDB 不翻译，
    中文名会是英文原样），再拉 en-US 补 name_en，一并持久化。
    """
    if not force:
        movie_map = db_service.get_genre_map("movie")
        tv_map = db_service.get_genre_map("tv")
        if movie_map and tv_map:
            return movie_map, tv_map

    maps: dict[str, dict[int, str]] = {}
    for mt in ("movie", "tv"):
        zh = _api_get(api_key, api_base, f"/genre/{mt}/list", {"language": "zh-CN"})
        en = _api_get(api_key, api_base, f"/genre/{mt}/list", {"language": "en-US"})
        en_names = {g.get("id"): g.get("name") or "" for g in (en.get("genres") or []) if g.get("id")}
        genres = []
        for g in zh.get("genres") or []:
            gid = g.get("id")
            if not gid:
                continue
            genres.append({"id": int(gid), "name": g.get("name") or "",
                           "name_en": en_names.get(gid, "")})
        if genres:
            db_service.replace_genre_map(mt, genres)
        maps[mt] = {int(g["id"]): g["name"] for g in genres}
    return maps.get("movie", {}), maps.get("tv", {})


def _run_list_plan(task: str, plan: list[dict], maps: tuple[dict, dict],
                   api_key: str, api_base: str) -> tuple[int, bool]:
    """按计划逐页拉取列表并批量 UPSERT；返回 (处理条数, 是否被取消)。"""
    movie_map, tv_map = maps
    total_pages = sum(p["pages"] for p in plan)
    done_pages = 0
    processed = 0

    for plan_item in plan:
        endpoint = plan_item["endpoint"]
        media_type = plan_item["media_type"]
        base_params = plan_item.get("params") or {}
        for page in range(1, plan_item["pages"] + 1):
            if jobs_state.is_cancel_requested(task):
                return processed, True
            batch: list[dict] = []
            try:
                data = _api_get(api_key, api_base, endpoint,
                                {**base_params, "page": page})
                for raw in data.get("results") or []:
                    if not raw.get("id"):
                        continue
                    batch.append(_normalize_item(raw, media_type, movie_map, tv_map))
            except Exception as exc:
                logger.warning("拉取失败 endpoint=%s page=%s error=%s", endpoint, page, exc)
            if batch:
                db_service.upsert_pool_items_batch(batch)
                processed += len(batch)
            done_pages += 1
            jobs_state.update(
                task,
                done_pages / max(total_pages, 1),
                f"已获取 {processed} 条（{done_pages}/{total_pages} 页）",
            )
    return processed, False


def fetch_initial_pool():
    """首次全量拉取精选约 1 万条，存入 metadata_pool。"""
    config = _config()
    api_key, api_base = config.TMDB_API_KEY, config.TMDB_API_BASE
    if not api_key:
        jobs_state.finish(TASK_INITIAL, label="未配置 TMDB API Key", error="no_api_key")
        return

    jobs_state.start(TASK_INITIAL, label="正在下载精选影视数据…")
    try:
        maps = ensure_genre_maps(api_key, api_base)
    except Exception as exc:
        logger.exception("题材映射拉取失败: %s", exc)
        maps = (db_service.get_genre_map("movie"), db_service.get_genre_map("tv"))

    inserted, cancelled = _run_list_plan(TASK_INITIAL, _FETCH_PLAN, maps, api_key, api_base)
    if cancelled:
        jobs_state.finish(TASK_INITIAL, label=f"已取消（已保留 {inserted} 条）", error="cancelled")
    else:
        jobs_state.finish(TASK_INITIAL, label=f"完成，共 {inserted} 条")


def backfill_genres():
    """题材回填：重放完整列表计划（约 800+ 页、零详情额度），补写 genre_ids/genres。

    UPSERT 冲突保护：已详情补全（detail_fetched=1）的条目若列表未带题材则保留原值；
    genre_ids/热度等字段随列表刷新。可随时取消，断点以已落库数据为准。
    """
    config = _config()
    api_key, api_base = config.TMDB_API_KEY, config.TMDB_API_BASE
    if not api_key:
        jobs_state.finish(TASK_GENRE_BACKFILL, label="未配置 TMDB API Key", error="no_api_key")
        return

    jobs_state.start(TASK_GENRE_BACKFILL, label="正在回填题材数据…")
    try:
        maps = ensure_genre_maps(api_key, api_base, force=True)
    except Exception as exc:
        logger.exception("题材映射拉取失败: %s", exc)
        maps = (db_service.get_genre_map("movie"), db_service.get_genre_map("tv"))
    if not maps[0] or not maps[1]:
        jobs_state.finish(TASK_GENRE_BACKFILL, label="题材映射不可用，请检查网络/API Key",
                          error="genre_map_unavailable")
        return

    processed, cancelled = _run_list_plan(TASK_GENRE_BACKFILL, _FETCH_PLAN, maps,
                                          api_key, api_base)
    missing = db_service.count_pool_missing_genres()
    if cancelled:
        jobs_state.finish(
            TASK_GENRE_BACKFILL,
            label=f"已取消（已处理 {processed} 条，仍缺题材 {missing} 条）",
            error="cancelled",
        )
    else:
        jobs_state.finish(
            TASK_GENRE_BACKFILL,
            label=f"完成，处理 {processed} 条，仍缺题材 {missing} 条",
        )


def refresh_trending():
    """每日 trending 刷新（约 400 条）。"""
    config = _config()
    api_key, api_base = config.TMDB_API_KEY, config.TMDB_API_BASE
    if not api_key:
        jobs_state.finish(TASK_TRENDING, label="未配置 TMDB API Key", error="no_api_key")
        return

    jobs_state.start(TASK_TRENDING, label="正在刷新热门榜…")
    try:
        maps = ensure_genre_maps(api_key, api_base)
    except Exception as exc:
        logger.warning("题材映射拉取失败: %s", exc)
        maps = (db_service.get_genre_map("movie"), db_service.get_genre_map("tv"))

    plan = [
        {"endpoint": "/trending/movie/week", "pages": 10, "media_type": "movie"},
        {"endpoint": "/trending/tv/week", "pages": 10, "media_type": "tv"},
    ]
    inserted, cancelled = _run_list_plan(TASK_TRENDING, plan, maps, api_key, api_base)
    if cancelled:
        jobs_state.finish(TASK_TRENDING, label=f"已取消（已刷新 {inserted} 条）", error="cancelled")
    else:
        jobs_state.finish(TASK_TRENDING, label=f"完成，共刷新 {inserted} 条")


def refresh_hotness():
    """热度快照：拉当前热门榜的 vote_count/popularity/vote_average 写入 hotness_series。

    只对 metadata_pool 已存在的条目落快照，避免存无关条目；
    每次执行用同一 fetched_at 形成一批快照点，多次执行即积累时间序列（30 天走势）。
    """
    config = _config()
    api_key = config.TMDB_API_KEY
    api_base = config.TMDB_API_BASE
    if not api_key:
        jobs_state.finish(TASK_HOTNESS, label="未配置 TMDB API Key", error="no_api_key")
        return

    jobs_state.start(TASK_HOTNESS, label="正在采集热度快照…")
    pool_ids = db_service.list_pool_ids()
    if not pool_ids:
        jobs_state.finish(TASK_HOTNESS, label="虚拟片库为空，先执行全量拉取", error="pool_empty")
        return

    total_pages = sum(p["pages"] for p in _HOTNESS_PLAN)
    done_pages = 0
    snapped = 0
    now_iso = datetime.now().isoformat(timespec="seconds")
    batch: list[dict] = []
    seen: set[str] = set()  # 本轮内按 pool_id 去重（榜单间重叠/跨页重复只留一条）
    for plan in _HOTNESS_PLAN:
        for page in range(1, plan["pages"] + 1):
            if jobs_state.is_cancel_requested(TASK_HOTNESS):
                jobs_state.finish(TASK_HOTNESS, label=f"已取消（已采集 {snapped} 条）", error="cancelled")
                return
            try:
                data = _api_get(api_key, api_base, plan["endpoint"], {"page": page})
                for raw in data.get("results") or []:
                    external_id = str(raw.get("id") or "")
                    pool_id = f"tmdb:{external_id}"
                    if not external_id or pool_id not in pool_ids or pool_id in seen:
                        continue
                    seen.add(pool_id)
                    batch.append({
                        "pool_id": pool_id,
                        "source": "tmdb",
                        "external_id": external_id,
                        "vote_average": raw.get("vote_average"),
                        "vote_count": raw.get("vote_count"),
                        "popularity": raw.get("popularity"),
                        "collection_count": None,
                        "fetched_at": now_iso,
                    })
            except Exception as exc:
                logger.warning("热度快照失败 endpoint=%s page=%s error=%s", plan["endpoint"], page, exc)
            done_pages += 1
            if len(batch) >= 200:
                db_service.insert_hotness_batch(batch)
                snapped += len(batch)
                batch = []
            jobs_state.update(TASK_HOTNESS, done_pages / total_pages, f"已采集 {snapped + len(batch)} 条热度")
    if batch:
        db_service.insert_hotness_batch(batch)
        snapped += len(batch)
    jobs_state.finish(TASK_HOTNESS, label=f"完成，共采集 {snapped} 条热度快照")


def fetch_detail(pool_id: str) -> dict | None:
    """按需懒加载某条目的 TMDB 详情（genres/runtime/status 等）。
    被路由层调用，不更新 jobs_state。
    """
    item = db_service.get_pool_item(pool_id)
    if not item:
        return None
    if item.get("detail_fetched"):
        return item
    config = _config()
    api_key = config.TMDB_API_KEY
    api_base = config.TMDB_API_BASE
    if not api_key:
        return item

    external_id = item.get("external_id") or ""
    media_type = item.get("media_type") or "movie"
    if media_type == "tv":
        endpoint = f"/tv/{external_id}"
    else:
        endpoint = f"/movie/{external_id}"
    data = _api_get(api_key, api_base, endpoint)
    if not data:
        return item

    # 详情 genres 是 [{id,name}]：统一走题材表归一（口径与列表一致，TV 英文名也能转中文），
    # 题材表缺失时才回退 API 原名；非空才覆盖，避免空结果冲掉已有题材。
    raw_genres = data.get("genres") or []
    detail_ids = [int(g.get("id")) for g in raw_genres if g.get("id")]
    movie_map = db_service.get_genre_map("movie")
    tv_map = db_service.get_genre_map("tv")
    genres = genre_taxonomy.map_genre_ids_to_names(detail_ids, media_type, movie_map, tv_map)
    if not genres:
        genres = [g.get("name") for g in raw_genres if g.get("name")]
    runtime = data.get("runtime")
    if not runtime and data.get("episode_run_time"):
        runtimes = data.get("episode_run_time")
        if isinstance(runtimes, list) and runtimes:
            runtime = runtimes[0]
    updates: dict[str, Any] = {
        "runtime": runtime,
        "status": data.get("status") or "",
        "overview": data.get("overview") or item.get("overview") or "",
        "detail_fetched": 1,
        "updated_at": datetime.now().isoformat(),
    }
    if genres:
        updates["genres"] = genres
    if detail_ids:
        updates["genre_ids"] = detail_ids
    item.update(updates)
    db_service.upsert_pool_item(item)
    return item


def prefetch_details(top: int = 2000) -> None:
    """详情预拉取（每日 06:00 调度，可手动触发/取消）。

    懒加载只能覆盖用户浏览过的条目，这里按 popularity Top N 主动补全，
    让推荐题材信号（genres）与详情面板对热门条目提前可用。
    复用 fetch_detail（单条早退 + 批量字段归一），逐条限速。
    """
    config = _config()
    if not config.TMDB_API_KEY:
        jobs_state.finish(TASK_DETAIL_PREFETCH, label="未配置 TMDB API Key", error="no_api_key")
        return
    jobs_state.start(TASK_DETAIL_PREFETCH, label=f"正在预拉取热门 Top {top} 详情…")
    top_items = db_service.get_top_pool_by_popularity(top)
    pending = [it["pool_id"] for it in top_items if not it.get("detail_fetched")]
    if not pending:
        jobs_state.finish(TASK_DETAIL_PREFETCH, label="热门条目详情均已补全，无需处理")
        return
    done = 0
    for pool_id in pending:
        if jobs_state.is_cancel_requested(TASK_DETAIL_PREFETCH):
            jobs_state.finish(
                TASK_DETAIL_PREFETCH,
                label=f"已取消（已补全 {done} 条）", error="cancelled")
            return
        try:
            fetch_detail(pool_id)
        except Exception as exc:
            logger.warning("详情预拉取失败 pool_id=%s error=%s", pool_id, exc)
        done += 1
        jobs_state.update(
            TASK_DETAIL_PREFETCH, done / len(pending),
            f"已补全 {done} / {len(pending)} 条详情")
        time.sleep(_REQUEST_INTERVAL)
    jobs_state.finish(TASK_DETAIL_PREFETCH, label=f"完成，共补全 {done} 条详情")


def pull_anime_top(top: int = 1000) -> None:
    """拉取 TMDB 日本动漫 Top N 入库（POST /api/jobs/anime-pull 手动触发）。

    用 discover/tv（动画流派 genre_id=16 + 原产国 JP + popularity 排序），
    与片库其余 TMDB 条目同一套 id/题材/热度链路，推荐端经
    「动画题材 + 日本」推断自动识别为动漫。条目按列表级数据入库
    （detail_fetched=0），详情由预拉取/懒加载补全。
    """
    config = _config()
    api_key, api_base = config.TMDB_API_KEY, config.TMDB_API_BASE
    if not api_key:
        jobs_state.finish(TASK_ANIME_PULL, label="未配置 TMDB API Key", error="no_api_key")
        return
    jobs_state.start(TASK_ANIME_PULL, label=f"正在拉取 TMDB 动漫 Top {top}…")
    try:
        maps = ensure_genre_maps(api_key, api_base)
    except Exception as exc:
        jobs_state.finish(TASK_ANIME_PULL, label=f"题材映射获取失败：{exc}", error="genre_map_failed")
        return
    pages = (top + 19) // 20  # discover 每页 20 条
    plan = [{
        "endpoint": "/discover/tv",
        "media_type": "tv",
        "pages": pages,
        "params": {
            "with_genres": 16,
            "with_origin_country": "JP",
            "sort_by": "popularity.desc",
            "language": "zh-CN",
        },
    }]
    processed, cancelled = _run_list_plan(TASK_ANIME_PULL, plan, maps, api_key, api_base)
    if cancelled:
        jobs_state.finish(TASK_ANIME_PULL, label=f"已取消（已入库 {processed} 条）", error="cancelled")
    else:
        jobs_state.finish(TASK_ANIME_PULL, label=f"完成，共处理 {processed} 条动漫")
