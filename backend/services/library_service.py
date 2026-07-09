"""
电影库管理服务
封装电影/剧集的缓存加载、统计计算、API 格式转换等业务逻辑
"""
import logging
import re
from collections import Counter
from datetime import datetime
from urllib.parse import quote, urlparse
from typing import Any, Optional

from . import db_service

logger = logging.getLogger(__name__)


def _get_webdav_client_class():
    try:
        from backend.core.webdav_client import WebDAVClient
    except ImportError:
        from core.webdav_client import WebDAVClient
    return WebDAVClient


def _get_app_config_class():
    try:
        from backend.config import AppConfig
    except ImportError:
        from config import AppConfig
    return AppConfig


def _get_openlist_manager():
    try:
        from backend.core.openlist_manager import openlist_manager
    except ImportError:
        from core.openlist_manager import openlist_manager
    return openlist_manager


def _get_openlist_client():
    try:
        from backend.core.openlist_client import openlist_client
    except ImportError:
        from core.openlist_client import openlist_client
    return openlist_client


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return [item for item in value if item]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r"[,/，、]", value) if part.strip()]
    return []


def _merge_unique_labels(*values: Any) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _as_list(value):
            label = str(item or "").strip()
            if not label:
                continue
            key = re.sub(r"\s+", "", label).lower()
            if key in seen:
                continue
            seen.add(key)
            labels.append(label)
    return labels


CATEGORY_API_MAPPING = {
    "动漫": "anime",
    "动画": "anime",
    "番剧": "anime",
    "电视剧": "series",
    "剧集": "series",
    "电影": "movie",
    "在线": "online",
}

EPISODE_MOVIE_SEPARATOR = "::"


def _api_category(category: Any) -> str:
    value = str(category or "movie").strip()
    return CATEGORY_API_MAPPING.get(value, value.lower())


def _api_categories(movie: dict) -> list[str]:
    primary_category = _api_category(movie.get("category"))
    categories = {primary_category}
    
    genres = _as_list(movie.get("genres"))
    has_animation_genre = any(
        str(g).lower() in {"animation", "动画", "アニメ", "anime", "动漫"}
        for g in genres
    )
    
    media_type = str(movie.get("media_type") or "").lower()
    is_animation_type = media_type == "动画"
    
    tmdb_media_type = str(movie.get("tmdb_media_type") or "").lower()
    
    has_animation = has_animation_genre or is_animation_type
    
    if primary_category == "movie" and has_animation:
        categories.add("anime")
    elif primary_category == "anime":
        if tmdb_media_type == "movie" or media_type == "电影":
            categories.add("movie")
    
    return sorted(list(categories))


def _identity_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?:^|\s)(s\d{1,2}|第[一二三四五六七八九十\d]+季|season\s*\d+)(?:$|\s)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _series_identity(movie: dict) -> str:
    for key in ("franchise", "series_title", "name", "search_title", "title"):
        value = _identity_text(movie.get(key))
        if value:
            return value
    return ""


def _resource_group_key(movie: dict) -> str:
    identity = _series_identity(movie)
    source_id = str(movie.get("source_id") or "")
    category = _api_category(movie.get("category"))
    base = f"{source_id}::{category}::{identity or movie.get('id') or movie.get('title')}"
    
    tmdb_media_type = str(movie.get("tmdb_media_type") or "").lower()
    is_movie_type = tmdb_media_type == "movie"
    
    if category == "movie" or is_movie_type:
        movie_title = _identity_text(movie.get("title") or movie.get("id"))
        return f"{base}::{movie_title}"

    special_type = str(movie.get("special_type") or "").strip()
    if special_type:
        title = _identity_text(movie.get("display_title") or movie.get("title") or movie.get("season_title"))
        return f"{base}::special::{special_type}::{title}"

    season = int(movie.get("season") or 1)
    return f"{base}::season::{season}"


def _has_display_suffix(movie: dict) -> bool:
    display = str(movie.get("display_title") or "").strip()
    title = str(movie.get("title") or "").strip()
    return bool(display and title and display != title)


def _movie_display_title(movie: dict) -> str:
    local_title = str(movie.get("title") or "未命名影片").strip()
    matched_title = str(movie.get("metadata_title") or "").strip()
    parsed_display = str(movie.get("display_title") or "").strip()
    if _has_display_suffix(movie):
        return parsed_display
    return matched_title or parsed_display or local_title


def _home_group_key(movie: dict) -> str:
    return _resource_group_key(movie)


def _home_representative_sort_key(movie: dict) -> tuple:
    return (
        1 if str(movie.get("version_title") or "").strip() else 0,
        int(movie.get("season") or 1),
        int(movie.get("part") or 0),
        str(movie.get("season_title") or ""),
        str(movie.get("id") or ""),
    )


def _collapse_home_movies(movies: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for movie in movies:
        grouped.setdefault(_home_group_key(movie), []).append(movie)

    representatives = []
    for items in grouped.values():
        chosen = sorted(items, key=_home_representative_sort_key)[0]
        clone = dict(chosen)
        clone["variant_count"] = len(items)
        clone["has_versions"] = any(str(item.get("version_title") or "").strip() for item in items)
        clone["season_count"] = len({
            (
                int(item.get("season") or 1),
                int(item.get("part") or 0),
                str(item.get("season_title") or ""),
                str(item.get("special_type") or ""),
            )
            for item in items
        })
        representatives.append(clone)

    representatives.sort(key=lambda item: (
        int(item.get("sort_bucket", 9)),
        str(item.get("sort_title") or item.get("title") or ""),
        int(item.get("season") or 1),
        str(item.get("id") or ""),
    ))
    return representatives


def _related_movies_for_detail(movie: dict) -> list[dict]:
    group_key = _resource_group_key(movie)
    if not group_key:
        return [movie]
    source_id = movie.get("source_id", "")
    related = []
    for item in load_library():
        if source_id and item.get("source_id") and item.get("source_id") != source_id:
            continue
        if _resource_group_key(item) == group_key:
            related.append(item)
    if not related:
        related = [movie]
    related.sort(key=lambda item: (
        int(item.get("season") or 1),
        int(item.get("part") or 0),
        str(item.get("season_title") or ""),
        str(item.get("version_title") or ""),
        str(item.get("title") or ""),
    ))
    return related


def get_recommendations(movie_id: str, limit: int = 12) -> list[dict]:
    movie = get_movie_by_id(movie_id)
    if not movie:
        return []

    library = load_library()
    movie_identity = _series_identity(movie)
    movie_category = _api_category(movie.get("category"))
    exclude_ids = {str(movie.get("id") or "")}

    recommendations = []

    if movie_identity:
        for item in library:
            if str(item.get("id") or "") in exclude_ids:
                continue
            if _series_identity(item) == movie_identity:
                recommendations.append(item)
                exclude_ids.add(str(item.get("id") or ""))
                if len(recommendations) >= limit:
                    return [movie_to_api_format(r) for r in recommendations]

    if movie_category:
        for item in library:
            if str(item.get("id") or "") in exclude_ids:
                continue
            if _api_category(item.get("category")) == movie_category:
                recommendations.append(item)
                exclude_ids.add(str(item.get("id") or ""))
                if len(recommendations) >= limit:
                    return [movie_to_api_format(r) for r in recommendations]

    return [movie_to_api_format(r) for r in recommendations]


def _split_episode_movie_id(episode_id: Optional[str]) -> tuple[str, str]:
    value = str(episode_id or "")
    if EPISODE_MOVIE_SEPARATOR not in value:
        return "", value
    movie_id, ep_id = value.split(EPISODE_MOVIE_SEPARATOR, 1)
    return movie_id, ep_id


def _build_episode_id(movie_id: str, ep_number: int) -> str:
    return f"{movie_id}{EPISODE_MOVIE_SEPARATOR}ep{ep_number}"

# 初始化数据库
db_service.init_db()


# ==================== 缓存读写 ====================

def load_library() -> list:
    """加载媒体库（从 SQLite 数据库）"""
    return db_service.load_library()


def save_library(movies: list) -> None:
    """保存媒体库（到 SQLite 数据库）"""
    db_service.save_library(movies)


def clear_library() -> None:
    """清除媒体库（从 SQLite 数据库）"""
    db_service.clear_library()


def get_movie_by_id(movie_id: str) -> Optional[dict]:
    """根据 ID 获取电影（从 SQLite 数据库）"""
    return db_service.get_movie_by_id(movie_id)


def update_playback(movie_id: str, episode_number: int, current_time: int, duration: int, watch_seconds_delta: int = 0, episode_id: str = "") -> None:
    """更新播放进度（到 SQLite 数据库）"""
    db_service.update_playback(movie_id, episode_number, current_time, duration, watch_seconds_delta, episode_id)


def _episode_progress_entry(playback: dict, episode_id: str = "", episode_number: int = 0) -> dict:
    episodes = playback.get("episodes") if isinstance(playback.get("episodes"), dict) else {}
    key = str(episode_id or "").strip()
    entry = episodes.get(key) if key else None
    if not isinstance(entry, dict) and episode_number:
        entry = episodes.get(f"ep{int(episode_number)}")
    return entry if isinstance(entry, dict) else {}


def _episode_progress_payload(entry: dict) -> dict:
    return {
        "episodeId": entry.get("episode_id", ""),
        "episodeNumber": entry.get("episode_number", 0),
        "currentTime": entry.get("current_time", 0),
        "duration": entry.get("duration", 0),
        "percent": entry.get("percent", 0),
        "lastPlayTime": entry.get("last_play_time", ""),
        "watchSeconds": entry.get("watch_seconds", 0),
    }


def _episode_progress_list(playback: dict) -> list[dict]:
    episodes = playback.get("episodes") if isinstance(playback.get("episodes"), dict) else {}
    items = [_episode_progress_payload(entry) for entry in episodes.values() if isinstance(entry, dict)]
    return sorted(items, key=lambda item: (int(item.get("episodeNumber") or 0), str(item.get("episodeId") or "")))


# ==================== 统计计算 ====================

def compute_stats(movies: list) -> dict:
    """根据电影列表计算分类统计"""
    stats = {
        "files": len(movies),
        "movies": 0,
        "series": 0,
        "anime": 0,
        "music": 0,
        "unmatched": 0,
        "watched": 0,
        "inProgress": 0,
        "completed": 0,
        "watchSeconds": 0,
    }
    for m in movies:
        cat = (m.get("category") or "").strip().lower()
        if cat in {"movie", "电影"}:
            stats["movies"] += 1
        elif cat in {"series", "电视剧", "剧集", "tv"}:
            stats["series"] += 1
        elif cat in {"anime", "动漫", "动画", "番剧"}:
            stats["anime"] += 1
        elif cat == "music":
            stats["music"] += 1
        else:
            stats["unmatched"] += 1
        playback = m.get("playback") if isinstance(m.get("playback"), dict) else {}
        try:
            percent = float(playback.get("percent") or 0)
        except (TypeError, ValueError):
            percent = 0
        try:
            current_time = int(float(playback.get("current_time") or 0))
        except (TypeError, ValueError):
            current_time = 0
        if percent > 0 or current_time > 0 or playback.get("last_play_time"):
            stats["watched"] += 1
        if 0 < percent < 90:
            stats["inProgress"] += 1
        if percent >= 90:
            stats["completed"] += 1
        try:
            watch_seconds = int(float(playback.get("watch_seconds") or 0))
        except (TypeError, ValueError):
            watch_seconds = 0
        stats["watchSeconds"] += max(0, watch_seconds or current_time)
    return stats


def compute_home_stats(movies: list) -> dict:
    """计算首页所需的统计信息"""
    remote = sum(1 for m in movies if m.get("source_type") in ("webdav", "openlist"))
    local = sum(1 for m in movies if m.get("source_type") == "local")
    fav = sum(1 for m in movies if m.get("is_favorite"))
    return {
        "total": len(movies),
        "remote": remote,
        "local": local,
        "favorite": fav,
    }


# ==================== API 格式转换 ====================

def compute_viewing_insights(movies: list) -> dict:
    """Build real viewing-stat data for the statistics page."""
    total = len(movies)
    watched_movies = [m for m in movies if _is_watched_movie(m)]
    watched_count = len(watched_movies)
    completed_count = sum(1 for m in movies if _playback_percent(m) >= 90)
    in_progress_count = sum(1 for m in movies if 0 < _playback_percent(m) < 90)
    favorite_count = sum(1 for m in movies if m.get("is_favorite"))
    watch_seconds = sum(_playback_watch_seconds(m) or _playback_current_time(m) for m in movies)
    progress_total = sum(_playback_percent(m) for m in watched_movies)
    rating_values = [_safe_float(m.get("rating")) for m in movies if _safe_float(m.get("rating")) > 0]

    category_counter = Counter(_category_label(_api_category(m.get("category"))) for m in movies)
    watched_category_counter = Counter(_category_label(_api_category(m.get("category"))) for m in watched_movies)
    source_counter = Counter(_source_label(m.get("source_type")) for m in movies)
    tag_counter = Counter()
    for movie in movies:
        for value in [*_as_list(movie.get("genres")), *_as_list(movie.get("countries")), *_as_list(movie.get("tags"))]:
            tag = str(value).strip()
            if tag:
                tag_counter[tag] += 1

    hour_counter = Counter()
    weekday_counter = Counter()
    recent_candidates = []
    for movie in watched_movies:
        played_at = _parse_datetime(_playback(movie).get("last_play_time"))
        if played_at:
            hour_counter[played_at.hour] += 1
            weekday_counter[played_at.weekday()] += 1
            recent_candidates.append((played_at, movie))

    recent_candidates.sort(key=lambda item: item[0], reverse=True)
    recent_history = []
    for played_at, movie in recent_candidates[:8]:
        item = movie_to_api_format(movie)
        item["lastPlayTime"] = played_at.isoformat()
        item["progressPercent"] = _playback_percent(movie)
        item["watchSeconds"] = _playback_watch_seconds(movie) or _playback_current_time(movie)
        recent_history.append(item)

    overview = {
        "total": total,
        "watched": watched_count,
        "completed": completed_count,
        "inProgress": in_progress_count,
        "favorite": favorite_count,
        "watchSeconds": watch_seconds,
        "watchHours": round(watch_seconds / 3600, 1),
        "completionRate": _ratio(completed_count, watched_count),
        "favoriteRate": _ratio(favorite_count, total),
        "avgProgress": round(progress_total / watched_count, 1) if watched_count else 0,
        "avgRating": round(sum(rating_values) / len(rating_values), 1) if rating_values else 0,
    }

    return {
        "overview": overview,
        "metrics": [
            {"key": "total", "label": "片库条目", "value": total, "unit": "部", "description": "当前片库中可识别的影视条目"},
            {"key": "watched", "label": "看过内容", "value": watched_count, "unit": "部", "description": "有播放进度或历史记录的条目"},
            {"key": "watchHours", "label": "累计时长", "value": overview["watchHours"], "unit": "小时", "description": "基于本地播放进度累计"},
            {"key": "completionRate", "label": "完播率", "value": overview["completionRate"], "unit": "%", "description": "播放进度达到 90% 的比例"},
        ],
        "categoryDistribution": _counter_distribution(category_counter, total),
        "watchedCategoryDistribution": _counter_distribution(watched_category_counter, watched_count),
        "sourceDistribution": _counter_distribution(source_counter, total),
        "tagDistribution": _counter_distribution(tag_counter, max(1, sum(tag_counter.values())), limit=14),
        "timeDistribution": [
            {"hour": hour, "label": f"{hour:02d}:00", "value": hour_counter.get(hour, 0), "percent": _ratio(hour_counter.get(hour, 0), max(1, max(hour_counter.values() or [1])))}
            for hour in range(24)
        ],
        "weekdayDistribution": [
            {"weekday": index, "label": label, "value": weekday_counter.get(index, 0), "percent": _ratio(weekday_counter.get(index, 0), max(1, max(weekday_counter.values() or [1])))}
            for index, label in enumerate(["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        ],
        "completionStats": [
            {"label": "已看完", "value": completed_count, "percent": _ratio(completed_count, total)},
            {"label": "观看中", "value": in_progress_count, "percent": _ratio(in_progress_count, total)},
            {"label": "未观看", "value": max(0, total - watched_count), "percent": _ratio(max(0, total - watched_count), total)},
        ],
        "recentHistory": recent_history,
    }


def _counter_distribution(counter: Counter, total: int, limit: int = 8) -> list:
    if not counter:
        return []
    base = max(1, total)
    return [{"label": label, "value": value, "percent": _ratio(value, base)} for label, value in counter.most_common(limit) if label and value]


def _category_label(category: str) -> str:
    return {"anime": "动漫", "series": "剧集", "movie": "电影", "music": "音乐", "documentary": "纪录"}.get(str(category or "").lower(), "其他")


def _source_label(source_type: Any) -> str:
    value = str(source_type or "local").strip().lower()
    if value == "openlist":
        return "OpenList"
    if value == "webdav":
        return "WebDAV"
    if value == "local":
        return "本地"
    return value or "其他"


def _playback(movie: dict) -> dict:
    playback = movie.get("playback")
    return playback if isinstance(playback, dict) else {}


def _playback_percent(movie: dict) -> float:
    return _safe_float(_playback(movie).get("percent"))


def _playback_current_time(movie: dict) -> int:
    return max(0, int(_safe_float(_playback(movie).get("current_time"))))


def _playback_watch_seconds(movie: dict) -> int:
    return max(0, int(_safe_float(_playback(movie).get("watch_seconds"))))


def _is_watched_movie(movie: dict) -> bool:
    playback = _playback(movie)
    return _playback_percent(movie) > 0 or _playback_current_time(movie) > 0 or bool(playback.get("last_play_time"))


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ratio(part: float, total: float) -> float:
    if not total:
        return 0
    return round(max(0, float(part)) / max(1, float(total)) * 100, 1)


def _clamp(value: float, lower: float = 0, upper: float = 100) -> float:
    return max(lower, min(upper, float(value)))


def movie_to_api_format(movie: dict) -> dict:
    """
    将内部电影数据转换为前端 API 文档定义的 MovieItem 格式
    """
    movie_id = movie.get("id", movie.get("title", ""))
    category = movie.get("category", "movie")
    source_type = movie.get("source_type", "local")
    local_title = movie.get("title", "未命名影片")
    matched_title = str(movie.get("metadata_title") or "").strip()
    display_title = _movie_display_title(movie)
    
    # 将中文 category 转换为前端能识别的英文格式
    category = _api_category(category)

    # 安全获取 playback 字段（防止类型错误）
    playback = movie.get("playback", {})
    if not isinstance(playback, dict):
        playback = {}

    genres = _as_list(movie.get("genres"))
    countries = _as_list(movie.get("countries"))
    languages = _as_list(movie.get("languages"))
    merged_tags = _merge_unique_labels(movie.get("tags"), genres, countries)

    parsed_type = str(movie.get("type") or "").lower()
    media_type = str(movie.get("media_type") or "").lower()
    
    if parsed_type:
        is_series = parsed_type == "series"
    elif media_type == "电影":
        is_series = False
    elif media_type == "剧集":
        is_series = True
    else:
        is_series = category in {"series", "tv"}
    
    item = {
        "id": movie_id,
        "title": display_title,
        "localTitle": local_title,
        "matchedTitle": matched_title,
        "type": "series" if is_series else "movie",
        "versionTitle": movie.get("version_title", ""),
        "variantCount": movie.get("variant_count", 1),
        "hasVersions": bool(movie.get("has_versions") or movie.get("version_title")),
        "seasonCount": movie.get("season_count", 1),
        "alias": movie.get("alias", []) if isinstance(movie.get("alias"), list) else [],
        "category": category,
        "categories": _api_categories(movie),
        "year": movie.get("year", movie.get("year_hint", 0)),
        "sourceType": source_type,
        "sourceName": movie.get("source_name", ""),
        "durationText": movie.get("duration", ""),
        "coverUrl": movie.get("cover_url") or "",
        "backdropUrl": movie.get("backdrop_url") or movie.get("cover_url") or "",
        "posterUrl": movie.get("cover_url") or "",
        "description": movie.get("intro", ""),
        "tags": merged_tags,
        "genres": genres,
        "countries": countries,
        "region": " / ".join(countries),
        "languages": languages,
        "metadataSource": movie.get("metadata_source", ""),
        "metadataLocked": bool(movie.get("metadata_locked")),
        "originalTitle": movie.get("original_title", ""),
        "tmdbId": movie.get("tmdb_id", ""),
        "tmdbMediaType": movie.get("tmdb_media_type", ""),
        "doubanUrl": movie.get("douban_url", ""),
        "voteCount": movie.get("vote_count", 0) or 0,
        "quality": movie.get("quality", ""),
        "videoCodec": movie.get("video_codec", ""),
        "audioInfo": movie.get("audio_info", ""),
        "subtitleInfo": movie.get("subtitle_info", ""),
        "score": movie.get("rating", 0) or 0,
        "isFavorite": movie.get("is_favorite", False),
        "progress": {
            "currentEpisode": playback.get("current_episode", 0),
            "currentEpisodeId": playback.get("current_episode_id", ""),
            "totalEpisodes": movie.get("episode_count", 0),
            "percent": playback.get("percent", 0),
            "currentTime": playback.get("current_time", 0),
            "duration": playback.get("duration", 0),
            "watchSeconds": playback.get("watch_seconds", 0),
            "lastPlayTime": playback.get("last_play_time", ""),
            "episodeProgress": _episode_progress_list(playback),
        },
        "episodeProgress": _episode_progress_list(playback),
        "updatedAt": movie.get("updated_at", ""),
    }

    # 安全处理 episodes（防止类型错误）
    raw_episodes = movie.get("episodes", [])
    if isinstance(raw_episodes, list):
        item["episodes"] = raw_episodes

    return item


# ==================== 详情页转换 ====================

def movie_to_detail(movie: dict) -> dict:
    """将电影数据转换为详情页格式（支持多季分集）"""
    detail = movie_to_api_format(movie)
    detail["description"] = movie.get("intro", "")
    detail["isFavorite"] = movie.get("is_favorite", False)
    detail["metadataLocked"] = bool(movie.get("metadata_locked"))
    # 支持两种字段名：path 和 file_path
    detail["filePath"] = movie.get("path", movie.get("file_path", ""))

    # 文件信息字段
    detail["fileSize"] = movie.get("file_size", "")
    detail["quality"] = movie.get("quality", "")
    detail["subtitleInfo"] = movie.get("subtitle_info", "")

    # 播放进度和记录
    playback = movie.get("playback", {})
    if isinstance(playback, dict):
        detail["playback"] = {
            "currentEpisode": playback.get("current_episode", 0),
            "currentEpisodeId": playback.get("current_episode_id", ""),
            "currentTime": playback.get("current_time", 0),
            "duration": playback.get("duration", 0),
            "lastPlayTime": playback.get("last_play_time", ""),
            "watchSeconds": playback.get("watch_seconds", 0),
            "episodeProgress": _episode_progress_list(playback),
        }
    else:
        detail["playback"] = {
            "currentEpisode": 0,
            "currentEpisodeId": "",
            "currentTime": 0,
            "duration": 0,
            "lastPlayTime": "",
            "watchSeconds": 0,
            "episodeProgress": [],
        }
    detail["lastPlayTime"] = detail["playback"]["lastPlayTime"]

    related_movies = _related_movies_for_detail(movie)
    version_names = {
        str(item.get("version_title") or "").strip()
        for item in related_movies
        if str(item.get("version_title") or "").strip()
    }
    has_explicit_versions = bool(version_names)
    seasons = []
    version_map: dict[str, dict[str, Any]] = {}
    for related in related_movies:
        season_number = int(related.get("season") or 1)
        season_title = str(related.get("season_title") or "").strip()
        explicit_version_title = str(related.get("version_title") or "").strip()
        part = int(related.get("part") or 0)
        version_title = season_title or f"第{season_number}季"
        if part and str(part) not in version_title:
            version_title = f"{version_title} Part {part}"
        if related.get("special_type"):
            version_title = f"{related.get('special_type')} {version_title}".strip()

        raw_episodes = related.get("episodes", [])
        episode_files = related.get("files", related.get("episode_files", []))
        related_playback = related.get("playback") if isinstance(related.get("playback"), dict) else {}
        episode_list = []
        if raw_episodes:
            for i, ep in enumerate(raw_episodes):
                if isinstance(ep, dict):
                    ep_number = int(ep.get("episode_number") or ep.get("episodeNumber") or i + 1)
                    ep_title = ep.get("title", f"第 {ep_number} 集")
                    ep_file = ep.get("file_path", "")
                else:
                    ep_number = int(ep) if isinstance(ep, (int, str)) and str(ep).isdigit() else i + 1
                    ep_title = f"第 {ep_number} 集"
                    ep_file = episode_files[i] if i < len(episode_files) else ""
                ep_id = _build_episode_id(str(related.get("id") or detail["id"]), ep_number)
                ep_progress = _episode_progress_payload(_episode_progress_entry(related_playback, ep_id, ep_number))
                episode_list.append({
                    "id": ep_id,
                    "episodeId": ep_id,
                    "movieId": related.get("id", detail["id"]),
                    "title": ep_title,
                    "episodeNumber": ep_number,
                    "durationText": "",
                    "playUrl": f"/api/movies/{related.get('id', detail['id'])}/play?episodeId={ep_id}",
                    "sourceType": related.get("source_type", ""),
                    "filePath": ep_file,
                    "progress": ep_progress,
                })

        season_entry = {
            "id": related.get("id", detail["id"]),
            "name": version_title,
            "title": version_title,
            "displayTitle": _movie_display_title(related),
            "description": related.get("intro", ""),
            "score": related.get("rating", 0) or 0,
            "year": related.get("year", related.get("year_hint", 0)),
            "tags": _merge_unique_labels(related.get("tags"), related.get("genres"), related.get("countries")),
            "versionName": version_title,
            "label": version_title,
            "seasonNumber": season_number,
            "seasonTitle": version_title,
            "versionTitle": explicit_version_title,
            "part": part,
            "movieId": related.get("id", detail["id"]),
            "coverUrl": related.get("cover_url") or "",
            "backdropUrl": related.get("backdrop_url") or related.get("cover_url") or "",
            "episodes": episode_list,
        }
        seasons.append(season_entry)
        if has_explicit_versions:
            version_name = explicit_version_title or "原版"
            version_entry = version_map.setdefault(version_name, {
                "id": f"version:{version_name}",
                "name": version_name,
                "title": version_name,
                "versionName": version_name,
                "label": version_name,
                "versionTitle": explicit_version_title,
                "seasons": [],
                "episodes": [],
            })
            version_entry["seasons"].append(season_entry)
            if not version_entry["episodes"]:
                version_entry["episodes"] = episode_list

    season_number = int(movie.get("season") or 1)
    season_title = str(movie.get("season_title") or "").strip()
    detail["currentSeasonNumber"] = season_number
    detail["seasonTitle"] = season_title or f"第{season_number}季"
    detail["seasons"] = seasons

    current_season = next((item for item in seasons if item.get("movieId") == movie.get("id")), seasons[0] if seasons else None)
    detail["episodes"] = current_season["episodes"] if current_season else []
    detail["versions"] = list(version_map.values()) if has_explicit_versions else []
    detail["hasVersions"] = len(detail["versions"]) > 1
    detail["hasMultipleSeasons"] = len(seasons) > 1

    return detail


# ==================== 播放地址解析 ====================

def resolve_play_url(movie: dict, episode_id: Optional[str], sources: list, refresh: bool = False) -> tuple[str, dict]:
    """
    根据电影数据解析播放 URL
    :return: (play_url, headers_dict)
    """
    source_type = movie.get("source_type", "local")
    file_path = ""
    episode_movie_id, normalized_episode_id = _split_episode_movie_id(episode_id)
    if episode_movie_id:
        target_movie = get_movie_by_id(episode_movie_id)
        if target_movie:
            movie = target_movie
            source_type = movie.get("source_type", "local")
        episode_id = normalized_episode_id

    if episode_id:
        # 支持旧格式 "{movie_id}_ep{number}" 和新格式 "{movie_id}::ep{number}"。
        ep_match = re.search(r'(?:^|[_:])ep(\d+)$', str(episode_id), re.IGNORECASE)
        ep_number = int(ep_match.group(1)) if ep_match else None

        episodes = movie.get("episodes", [])
        episode_files = movie.get("files", movie.get("episode_files", []))
        
        # 方法1: 从 episodes 字典列表中查找
        if episodes and isinstance(episodes[0], dict):
            for ep in episodes:
                if isinstance(ep, dict) and ep.get("id") == episode_id:
                    file_path = ep.get("file_path", "")
                    break
        
        # 方法2: 从整数列表中按索引查找（使用循环索引而不是集数）
        if not file_path and episodes and isinstance(episodes[0], int) and ep_number is not None:
            for i, ep in enumerate(episodes):
                if int(ep) == ep_number:
                    if i < len(episode_files):
                        file_path = episode_files[i]
                    break
        if not file_path and episode_files and ep_number is not None:
            index = ep_number - 1
            if 0 <= index < len(episode_files):
                file_path = episode_files[index]
    else:
        file_path = movie.get("path") or movie.get("file_path", "")
        if not file_path:
            episode_files = movie.get("files", movie.get("episode_files", []))
            file_path = episode_files[0] if episode_files else ""

    headers = {}
    if not file_path:
        raise RuntimeError("未找到可播放文件路径")

    if source_type == "webdav":
        WebDAVClient = _get_webdav_client_class()
        source = next(
            (s for s in sources if s.get("id") == movie.get("source_id")), None
        )
        if source:
            client = WebDAVClient(
                host=_resolve_webdav_source_base_url(source),
                username=source.get("username", ""),
                password=source.get("password", ""),
            )
            file_path, headers = client.get_stream_url(file_path)

    if source_type == "openlist":
        source = next(
            (s for s in sources if s.get("id") == movie.get("source_id")), None
        )
        file_path, headers = _resolve_openlist_play_url(file_path, source, refresh=refresh)

    if source_type == "online":
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        }

    return file_path, headers


def _resolve_openlist_play_url(path: str, source: Optional[dict] = None, refresh: bool = False) -> tuple[str, dict]:
    if not path:
        return path, {}

    AppConfig = _get_app_config_class()
    openlist_manager = _get_openlist_manager()
    openlist_client = _get_openlist_client()

    config = AppConfig()
    config.load_config()
    status = openlist_manager.get_status()
    if not config.OPENLIST_ADMIN_PASSWORD:
        raise RuntimeError("缺少 OpenList 管理员密码，无法解析播放地址")

    base_url = _openlist_playback_base_url(openlist_manager, config, status, source)
    if not base_url:
        raise RuntimeError("OpenList 服务未运行，无法解析播放地址")
    openlist_client.set_base_url(base_url)
    result = openlist_client.get_file(config.OPENLIST_ADMIN_PASSWORD, path, refresh=refresh)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    play_url = _pick_openlist_file_url(data)
    signed_url = _openlist_signed_download_url(base_url, path, data)
    if not play_url and signed_url:
        play_url = signed_url
    if not play_url:
        raise RuntimeError("OpenList 未返回可播放直链")

    headers = _pick_openlist_headers(data)
    headers.update(_default_openlist_play_headers(play_url, source))
    return play_url, headers


def _openlist_playback_base_url(openlist_manager, config, status: dict, source: Optional[dict] = None) -> str:
    if status.get("status") == "running":
        return str(status.get("base_url") or f"http://127.0.0.1:{status.get('port', 5244)}").rstrip("/")

    if getattr(config, "OPENLIST_ENABLED", False) and getattr(config, "OPENLIST_AUTO_START", False):
        try:
            start_result = openlist_manager.start()
            if start_result.get("success"):
                login_result = openlist_manager.ensure_logged_in()
                if not login_result.get("success"):
                    logger.warning("OpenList auto-login failed before playback: %s", login_result.get("message", ""))
                status = openlist_manager.get_status()
                if status.get("status") == "running":
                    return str(status.get("base_url") or f"http://127.0.0.1:{status.get('port', 5244)}").rstrip("/")
        except Exception as exc:
            logger.warning("OpenList auto-start failed before playback: %s", exc)

    source_url = str((source or {}).get("path") or "").strip().rstrip("/")
    if source_url.startswith(("http://", "https://")):
        return source_url
    return ""


def _openlist_signed_download_url(base_url: str, path: str, data: dict) -> str:
    sign = str(data.get("sign") or "").strip()
    if not sign:
        return ""
    api_path = str(path or "").strip()
    if not api_path.startswith("/"):
        api_path = "/" + api_path
    return f"{base_url.rstrip('/')}/d{quote(api_path, safe='/')}?sign={quote(sign, safe='')}"


def _pick_openlist_file_url(data: dict) -> str:
    for key in ("raw_url", "rawUrl", "url", "download_url", "downloadUrl"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("content", "provider", "file"):
        nested = data.get(key)
        if isinstance(nested, dict):
            value = _pick_openlist_file_url(nested)
            if value:
                return value
    return ""


def _pick_openlist_headers(data: dict) -> dict:
    headers = {}
    for key in ("headers", "header"):
        value = data.get(key)
        if isinstance(value, dict):
            headers.update({str(k): str(v) for k, v in value.items() if v is not None})
    return headers


def _default_openlist_play_headers(play_url: str, source: Optional[dict] = None) -> dict:
    host = urlparse(play_url).netloc.lower()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    if "quark.cn" in host:
        headers["Referer"] = "https://pan.quark.cn/"
        headers["Origin"] = "https://pan.quark.cn"
        cookie = _openlist_source_cookie(source)
        if cookie:
            headers["Cookie"] = cookie
    return headers


def _openlist_source_cookie(source: Optional[dict]) -> str:
    if not source:
        return ""
    addition = source.get("addition") or {}
    if isinstance(addition, dict):
        cookie = str(addition.get("cookie") or "").strip()
        if cookie and cookie != "******":
            return cookie
    cookie = str(source.get("cookie") or "").strip()
    if cookie and cookie != "******":
        return cookie
    return ""


def _resolve_webdav_source_base_url(source: dict) -> str:
    """Use the saved WebDAV URL, auto-upgrading old root URLs to /dav when needed."""
    WebDAVClient = _get_webdav_client_class()

    base = str(source.get("path") or "").strip().rstrip("/")
    if not base:
        return ""

    candidates = [base]
    parsed = urlparse(base)
    if not parsed.path or parsed.path == "/":
        candidates.append(base + "/dav")

    for candidate in dict.fromkeys(candidates):
        try:
            client = WebDAVClient(
                host=candidate,
                username=source.get("username", ""),
                password=source.get("password", ""),
            )
            if client.verify_connection():
                return candidate
        except Exception:
            continue
    return base


# ==================== 首页数据构建 ====================

def build_home_data(movies: list, category: Optional[str], limit: int) -> dict:
    """构建首页数据"""
    if category and category != "all":
        target_category = str(category).lower()
        movies = [
            m for m in movies
            if target_category in _api_categories(m)
        ]
    movies = _collapse_home_movies(movies)

    stats = compute_home_stats(movies)
    hero = []
    for m in movies[:5]:
        api_item = movie_to_api_format(m)
        hero.append({
            "id": api_item["id"],
            "title": api_item["title"],
            "category": api_item["category"],
            "year": api_item["year"],
            "sourceType": api_item["sourceType"],
            "sourceName": api_item["sourceName"],
            "durationText": api_item["durationText"],
            "backdropUrl": api_item.get("backdropUrl", api_item.get("coverUrl", "")),
            "tags": api_item["tags"],
        })

    items = [movie_to_api_format(m) for m in movies[:limit]]

    return {
        "stats": stats,
        "hero": hero,
        "items": items,
    }
