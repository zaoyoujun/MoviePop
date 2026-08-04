"""
电影库管理服务
封装电影/剧集的缓存加载、统计计算、API 格式转换等业务逻辑
"""
import hashlib
import logging
import math
import re
from collections import Counter
from datetime import datetime
from urllib.parse import quote, unquote, urlparse
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


def _category_from_media_path(movie: dict) -> str:
    """Recover the scanned collection category from a media path when present.

    Older scans may have had ``category`` overwritten by incomplete provider
    metadata.  The path is the original scan input, so its collection segment
    is the more reliable primary browse category in that situation.
    """
    for key in ("file_path", "path"):
        raw_path = str(movie.get(key) or "").strip()
        if not raw_path:
            continue
        parts = [part.strip() for part in unquote(raw_path).replace("\\", "/").split("/") if part.strip()]
        for part in parts:
            category = _api_category(part)
            if category in {"anime", "series", "movie"}:
                return category
    return ""


def _primary_browse_category(movie: dict) -> str:
    """Return the directory-backed primary category, with legacy fallback."""
    return _category_from_media_path(movie) or _api_category(movie.get("category"))


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _has_animation_metadata(movie: dict) -> bool:
    """Detect animation from scraper metadata without changing directory category."""
    animation_labels = {
        "animation", "animated", "anime", "cartoon",
        "动画", "动画片", "动漫", "番剧", "アニメ",
    }
    labels = [*_as_list(movie.get("genres")), *_as_list(movie.get("tags"))]
    for label in labels:
        normalized = re.sub(r"\s+", "", str(label or "")).lower()
        if normalized in animation_labels:
            return True
    return str(movie.get("media_type") or "").strip().lower() in {"动画", "animation", "anime"}


def _api_categories(movie: dict) -> list[str]:
    primary_category = _primary_browse_category(movie)
    categories = {primary_category}

    media_type = str(movie.get("media_type") or "").lower()
    tmdb_media_type = str(movie.get("tmdb_media_type") or "").lower()
    has_animation = _has_animation_metadata(movie)
    is_not_series = "is_series" in movie and not _as_bool(movie.get("is_series"))
    special_label = " ".join(
        str(movie.get(key) or "")
        for key in ("special_type", "season_title", "chapter_name", "version_title")
    ).lower()
    is_theatrical_release = any(label in special_label for label in ("剧场版", "电影版", "theatrical"))

    # The directory decides the primary category. Scraper metadata contributes
    # secondary browse categories, so animation films remain visible as movies.
    if primary_category == "movie" and has_animation:
        categories.add("anime")
    elif primary_category == "anime":
        if tmdb_media_type == "movie" or media_type == "电影" or is_not_series or is_theatrical_release:
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
    tmdb_media_type = str(movie.get("tmdb_media_type") or "").lower()
    category = _primary_browse_category(movie)

    # Provider and directory categories can differ between seasons (for
    # example anime vs. TV).  The parser's is_series flag remains available
    # even when a selected provider does not return a TMDB media type.
    is_series = _as_bool(movie.get("is_series")) or tmdb_media_type == "tv"
    group_category = "series" if is_series else category
    base = f"{source_id}::{group_category}::{identity or movie.get('id') or movie.get('title')}"

    is_movie_type = tmdb_media_type == "movie"
    
    if is_movie_type or (category == "movie" and not is_series):
        movie_title = _identity_text(movie.get("title") or movie.get("id"))
        return f"{base}::{movie_title}"

    special_type = str(movie.get("special_type") or "").strip()
    if special_type:
        title = _identity_text(movie.get("display_title") or movie.get("title") or movie.get("season_title"))
        return f"{base}::special::{special_type}::{title}"

    return base


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


def _continue_context_key(value: Any) -> str:
    """Create a forgiving key for de-duplicating compact playback labels."""
    return re.sub(r"[\s·•|/、，,;；:：_\-]+", "", str(value or "").strip()).casefold()


def _continue_episode_number(movie: dict, playback: dict) -> int:
    """Read the active episode number from persisted playback data safely."""
    for value in (playback.get("current_episode"), playback.get("episode_number")):
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            number = 0
        if number > 0:
            return number

    episode_id = str(playback.get("current_episode_id") or playback.get("episode_id") or "").strip()
    if episode_id:
        episodes = playback.get("episodes") if isinstance(playback.get("episodes"), dict) else {}
        entry = episodes.get(episode_id) if isinstance(episodes.get(episode_id), dict) else {}
        try:
            number = int(entry.get("episode_number") or 0)
        except (TypeError, ValueError):
            number = 0
        if number > 0:
            return number

        match = re.search(r"(?:ep|e)(\d{1,4})(?:\D|$)", episode_id, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _continue_episode_title(movie: dict, episode_number: int) -> str:
    """Return a non-generic episode title when the scanner retained one."""
    if episode_number <= 0:
        return ""
    raw_episodes = movie.get("episodes")
    if not isinstance(raw_episodes, list):
        return ""

    for index, episode in enumerate(raw_episodes):
        if isinstance(episode, dict):
            try:
                number = int(episode.get("episode_number") or episode.get("episodeNumber") or index + 1)
            except (TypeError, ValueError):
                number = index + 1
            title = str(episode.get("title") or episode.get("name") or "").strip()
        else:
            try:
                number = int(episode)
            except (TypeError, ValueError):
                number = index + 1
            title = ""
        if number != episode_number or not title:
            continue

        normalized_title = _continue_context_key(title)
        if re.fullmatch(
            r"(?:第?\s*[一二三四五六七八九十百零〇两\d]+\s*集|(?:episode|ep|e)\s*0*\d+)",
            title,
            re.IGNORECASE,
        ):
            return ""
        generic_titles = {
            _continue_context_key(f"第 {episode_number} 集"),
            _continue_context_key(f"E{episode_number}"),
            _continue_context_key(f"EP{episode_number}"),
            str(episode_number),
        }
        return "" if normalized_title in generic_titles else title
    return ""


def _is_plain_season_label(value: Any) -> bool:
    """Whether a custom season value only repeats the season number."""
    text = str(value or "").strip()
    if not text:
        return False
    return bool(re.fullmatch(
        r"(?:第?\s*[一二三四五六七八九十百零〇两\d]+\s*季|season\s*\d+|s\d+)",
        text,
        re.IGNORECASE,
    ))


def build_continue_watching_context(movie: dict) -> dict[str, Any]:
    """Build concise, de-duplicated labels for a single resume-history record.

    Home cards intentionally keep the work title as their primary title.  This
    payload carries the resource axes that would otherwise be invisible when a
    show has multiple seasons or a film has multiple encodes.
    """
    playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
    is_series = _as_bool(movie.get("is_series")) or str(movie.get("type") or "").strip().lower() == "series" or str(movie.get("tmdb_media_type") or "").strip().lower() == "tv"

    parts: list[str] = []
    seen: set[str] = set()

    def add(label: Any) -> str:
        text = str(label or "").strip()
        key = _continue_context_key(text)
        if text and key and key not in seen:
            seen.add(key)
            parts.append(text)
            return text
        return ""

    season_parts: list[str] = []
    if is_series:
        try:
            season_number = int(movie.get("season") or 1)
        except (TypeError, ValueError):
            season_number = 1
        raw_season_title = str(movie.get("season_title") or "").strip()
        custom_season_title = add(raw_season_title)
        if custom_season_title:
            season_parts.append(custom_season_title)
        # A descriptive custom name benefits from the numeric axis too; a
        # plain "第一季" / "Season 1" is already that axis and must not repeat.
        if season_number > 0 and (not custom_season_title or not _is_plain_season_label(raw_season_title)):
            numeric_season = add(f"第 {season_number} 季")
            if numeric_season:
                season_parts.append(numeric_season)

    version_label = add(movie.get("version_title"))
    chapter_label = str(movie.get("chapter_name") or "").strip()
    if not chapter_label:
        try:
            part = int(movie.get("part") or 0)
        except (TypeError, ValueError):
            part = 0
        if part > 0:
            chapter_label = f"第 {part} 部"
    chapter_label = add(chapter_label)

    episode_number = _continue_episode_number(movie, playback)
    episode_parts: list[str] = []
    if episode_number > 0:
        episode_parts.append(add(f"第 {episode_number} 集"))
        episode_title = add(_continue_episode_title(movie, episode_number))
        if episode_title:
            episode_parts.append(episode_title)

    season_label = " · ".join(part for part in season_parts if part)
    episode_label = " · ".join(part for part in episode_parts if part)
    return {
        "text": " · ".join(parts),
        "parts": parts,
        "seasonLabel": season_label,
        "versionLabel": version_label,
        "chapterLabel": chapter_label,
        "episodeLabel": episode_label,
    }


def continue_watching_api_fields(movie: dict) -> dict[str, Any]:
    """Expose the compact resume labels using the API's camelCase convention."""
    context = build_continue_watching_context(movie)
    playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
    episode_key = str(playback.get("current_episode_id") or "").strip()
    if not episode_key:
        episode_number = _continue_episode_number(movie, playback)
        episode_key = f"ep{episode_number}" if episode_number > 0 else "default"
    resource_key = str(movie.get("id") or movie.get("file_path") or movie.get("path") or movie.get("title") or "unknown")
    return {
        "continueContext": context["text"],
        "continueContextParts": context["parts"],
        "continueSeasonLabel": context["seasonLabel"],
        "continueVersionLabel": context["versionLabel"],
        "continueChapterLabel": context["chapterLabel"],
        "continueEpisodeLabel": context["episodeLabel"],
        # Keep Vue's card identity independent from a shared work title.
        "continueCardKey": f"{resource_key}::{episode_key}",
    }


def history_item_to_api_format(movie: dict) -> dict[str, Any]:
    """Return the history-specific API representation for one physical resource."""
    item = movie_to_api_format(movie)
    playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
    item["playback"] = {
        "currentEpisode": playback.get("current_episode", 0),
        "currentTime": playback.get("current_time", 0),
        "duration": playback.get("duration", 0),
        "percent": playback.get("percent", 0),
        "lastPlayTime": playback.get("last_play_time", ""),
        "watchSeconds": playback.get("watch_seconds", 0),
    }
    item["lastPlayTime"] = playback.get("last_play_time", "")
    item["watchSeconds"] = playback.get("watch_seconds", 0)
    item.update(continue_watching_api_fields(movie))
    return item


def continue_watching_records(movies: list[dict], page: int = 1, page_size: int = 24) -> tuple[list[dict], int]:
    """Select a page of physical resources with playback history, newest first."""
    records = [
        movie for movie in movies
        if isinstance(movie.get("playback"), dict) and movie.get("playback", {}).get("last_play_time")
    ]
    records.sort(key=lambda movie: str(movie.get("playback", {}).get("last_play_time") or ""), reverse=True)
    total = len(records)
    try:
        page_number = max(1, int(page or 1))
    except (TypeError, ValueError):
        page_number = 1
    try:
        size = max(1, int(page_size or 24))
    except (TypeError, ValueError):
        size = 24
    start = (page_number - 1) * size
    return records[start:start + size], total


def _home_group_key(movie: dict) -> str:
    return _resource_group_key(movie)


def _home_representative_sort_key(movie: dict) -> tuple:
    return (
        0 if _as_bool(movie.get("home_display")) else 1,
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


def set_home_presentation(movie_id: str) -> Optional[dict]:
    """Persist one season, chapter, or edition as a work's home presentation."""
    target_id = str(movie_id or "").strip()
    if not target_id:
        return None

    movies = load_library()
    target = next((movie for movie in movies if str(movie.get("id") or "") == target_id), None)
    if not target:
        return None

    group_key = _home_group_key(target)
    for movie in movies:
        if _home_group_key(movie) == group_key:
            movie["home_display"] = str(movie.get("id") or "") == target_id

    save_library(movies)
    return target


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


def _detail_label_key(value: Any) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", str(value or "")).casefold()


def _detail_season_axis(movie: dict) -> tuple[str, str, int]:
    """Return the season subtitle and chapter fields used by detail clients.

    New scans persist ``chapter_name`` directly.  The small legacy fallback
    keeps existing libraries correct until their next scan: older databases
    stored a folder such as ``袭击篇 #1`` only as ``season_title``.
    """
    season_title = str(movie.get("season_title") or "").strip()
    chapter_name = str(movie.get("chapter_name") or "").strip()
    part = int(movie.get("part") or 0)
    version_title = str(movie.get("version_title") or "").strip()

    if version_title and _detail_label_key(version_title) == _detail_label_key(season_title):
        season_title = ""

    if part and re.fullmatch(rf"part\s*{part}", season_title, re.IGNORECASE):
        season_title = ""

    if not chapter_name and part:
        legacy_match = re.fullmatch(r"\s*(?P<name>[\u4e00-\u9fff]{2,}[篇章])\s*#\s*(?P<part>\d+)\s*", season_title)
        if legacy_match and int(legacy_match.group("part")) == part:
            chapter_name = legacy_match.group("name")
            season_title = ""

    return season_title, chapter_name, part


def _media_structure_for_detail(related_movies: list[dict]) -> dict:
    """Build explicit season, variant and chapter axes for detail consumers."""
    variants: dict[str, dict] = {}
    seasons: dict[str, dict] = {}

    for related in related_movies:
        season_number = int(related.get("season") or 1)
        season_title, chapter_name, part = _detail_season_axis(related)
        version_title = str(related.get("version_title") or "").strip()
        season_key = f"S{season_number}:{season_title}"
        variant_key = version_title or "default"
        variant = variants.setdefault(variant_key, {
            "id": f"variant:{variant_key}",
            "name": version_title or "默认版本",
            "versionTitle": version_title,
            "isDefault": not version_title,
            "seasons": [],
        })
        season = seasons.setdefault(season_key, {
            "id": f"season:{season_key}",
            "seasonNumber": season_number,
            "seasonTitle": season_title,
            "chapters": [],
        })
        chapter_label = chapter_name or (f"Part {part}" if part else "正片")
        entry = {
            "movieId": related.get("id", ""),
            "seasonNumber": season_number,
            "seasonTitle": season_title,
            "versionTitle": version_title,
            "chapterName": chapter_name,
            "part": part,
            "label": chapter_label,
            "episodeCount": int(related.get("episode_count") or len(related.get("episodes") or [])),
        }
        if not any(item.get("movieId") == entry["movieId"] for item in season["chapters"]):
            season["chapters"].append(entry)
        variant["seasons"].append(entry)

    for season in seasons.values():
        season["chapters"].sort(key=lambda item: (item["part"], item["chapterName"], item["versionTitle"]))
    for variant in variants.values():
        variant["seasons"].sort(key=lambda item: (item["seasonNumber"], item["part"], item["chapterName"]))

    variant_items = list(variants.values())
    variant_items.sort(key=lambda item: (not item["isDefault"], item["name"]))
    season_items = sorted(seasons.values(), key=lambda item: (item["seasonNumber"], item["seasonTitle"]))
    return {"variants": variant_items, "seasons": season_items}


def get_recommendations(movie_id: str, limit: int = 12) -> list[dict]:
    movie = get_movie_by_id(movie_id)
    if not movie:
        return []

    library = load_library()
    movie_identity = _series_identity(movie)
    movie_category = _primary_browse_category(movie)
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
            if _primary_browse_category(item) == movie_category:
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


def upsert_movie(movie: dict) -> None:
    """Persist one scanned resource while keeping all other resources available."""
    db_service.upsert_movie(movie)


def remove_source_movies_not_in(source_id: str, movie_ids: list[str]) -> None:
    """Remove files that disappeared from one source after its scan finishes."""
    db_service.remove_source_movies_not_in(source_id, movie_ids)


def remove_source_movies_outside_paths(source_id: str, selected_paths: list[str]) -> int:
    """Drop stale records as soon as a source's selected directories change."""
    return db_service.remove_source_movies_outside_paths(source_id, selected_paths)


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
        cat = _primary_browse_category(m)
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
    logical_titles = len(_collapse_home_movies(movies))
    watched_movies = [m for m in movies if _is_watched_movie(m)]
    watched_count = len(watched_movies)
    completed_count = sum(1 for m in movies if _playback_percent(m) >= 90)
    in_progress_count = sum(1 for m in movies if 0 < _playback_percent(m) < 90)
    favorite_count = sum(1 for m in movies if m.get("is_favorite"))
    watch_seconds = sum(_playback_watch_seconds(m) or _playback_current_time(m) for m in movies)
    progress_total = sum(_playback_percent(m) for m in watched_movies)
    rating_values = [_safe_float(m.get("rating")) for m in movies if _safe_float(m.get("rating")) > 0]

    category_counter = Counter(_category_label(_primary_browse_category(m)) for m in movies)
    watched_category_counter = Counter(_category_label(_primary_browse_category(m)) for m in watched_movies)
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
        "resourceEntries": total,
        "logicalTitles": logical_titles,
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
    category = _primary_browse_category(movie)

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
    tmdb_media_type = str(movie.get("tmdb_media_type") or "").lower()
    
    if parsed_type:
        is_series = parsed_type == "series"
    elif tmdb_media_type == "tv":
        is_series = True
    elif tmdb_media_type == "movie":
        is_series = False
    elif media_type == "电影":
        is_series = False
    elif media_type == "剧集":
        is_series = True
    elif "is_series" in movie:
        is_series = _as_bool(movie.get("is_series"))
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
        "homeDisplay": _as_bool(movie.get("home_display")),
        "seasonCount": movie.get("season_count", 1),
        "alias": movie.get("alias", []) if isinstance(movie.get("alias"), list) else [],
        "category": category,
        "categories": _api_categories(movie),
        "year": movie.get("year", movie.get("year_hint", 0)),
        "releaseDate": movie.get("release_date") or "",
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
    detail["mediaStructure"] = _media_structure_for_detail(related_movies)
    
    season_map: dict[int, dict[str, Any]] = {}
    version_map: dict[str, dict[str, Any]] = {}
    all_seasons = []
    
    for related in related_movies:
        season_number = int(related.get("season") or 1)
        season_title, chapter_name, part = _detail_season_axis(related)
        explicit_version_title = str(related.get("version_title") or "").strip()
        
        season_name = season_title or f"第{season_number}季"
        
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

        if season_number not in season_map:
            season_map[season_number] = {
                "id": f"season:{season_number}",
                "name": season_name,
                "title": season_name,
                "seasonNumber": season_number,
                "seasonTitle": season_title,
                "displayTitle": _movie_display_title(related),
                "description": related.get("intro", ""),
                "score": related.get("rating", 0) or 0,
                "year": related.get("year", related.get("year_hint", 0)),
                "releaseDate": related.get("release_date") or "",
                "tags": _merge_unique_labels(related.get("tags"), related.get("genres"), related.get("countries")),
                "coverUrl": related.get("cover_url") or "",
                "backdropUrl": related.get("backdrop_url") or related.get("cover_url") or "",
                "episodes": [],
                "versions": [],
            }
        
        chapter_name = chapter_name or (f"Part {part}" if part else "")
        
        if chapter_name:
            version_name = f"{season_name} {chapter_name}"
        elif explicit_version_title:
            version_name = explicit_version_title
        else:
            version_name = season_name
        
        if version_name not in version_map:
            version_map[version_name] = {
                "id": f"version:{version_name}",
                "name": version_name,
                "title": version_name,
                "versionTitle": explicit_version_title or chapter_name,
                "episodes": [],
                "seasons": [],
            }
        
        season_entry = {
            "id": related.get("id", detail["id"]),
            "name": season_name,
            "title": season_name,
            "displayTitle": _movie_display_title(related),
            "description": related.get("intro", ""),
            "score": related.get("rating", 0) or 0,
            "year": related.get("year", related.get("year_hint", 0)),
            "releaseDate": related.get("release_date") or "",
            "tags": _merge_unique_labels(related.get("tags"), related.get("genres"), related.get("countries")),
            "versionName": version_name,
            "label": chapter_name if chapter_name else season_name,
            "seasonNumber": season_number,
            "seasonTitle": season_title,
            "versionTitle": explicit_version_title or chapter_name,
            "part": part,
            "chapterName": chapter_name,
            "movieId": related.get("id", detail["id"]),
            "coverUrl": related.get("cover_url") or "",
            "backdropUrl": related.get("backdrop_url") or related.get("cover_url") or "",
            "episodes": episode_list,
        }
        
        season_map[season_number]["episodes"].extend(episode_list)
        season_map[season_number]["versions"].append(version_name)
        
        version_map[version_name]["episodes"].extend(episode_list)
        version_map[version_name]["seasons"].append(season_entry)
        
        all_seasons.append(season_entry)

    detail["seasons"] = sorted(season_map.values(), key=lambda x: x["seasonNumber"])
    detail["versions"] = list(version_map.values())
    # `versions` is kept for existing clients and may contain seasons.  The
    # explicit structure distinguishes actual media variants from season choice.
    detail["hasVersions"] = len(detail["mediaStructure"]["variants"]) > 1
    detail["hasMultipleSeasons"] = len(detail["seasons"]) > 1
    
    season_number = int(movie.get("season") or 1)
    season_title, _, _ = _detail_season_axis(movie)
    detail["currentSeasonNumber"] = season_number
    detail["seasonTitle"] = season_title or f"第{season_number}季"

    current_season = next((item for item in all_seasons if item.get("movieId") == movie.get("id")), all_seasons[0] if all_seasons else None)
    detail["episodes"] = current_season["episodes"] if current_season else []

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

def _home_timestamp(value: Any) -> float:
    """Return a comparable timestamp without letting malformed legacy dates affect ranking."""
    parsed = _parse_datetime(value)
    if not parsed:
        return 0.0
    try:
        return parsed.timestamp()
    except (OSError, OverflowError, ValueError):
        return 0.0


def _normalized_rating(movie: dict) -> float:
    """Normalize common 10-point and 100-point scraper scores to 0..1."""
    rating = max(0.0, _safe_float(movie.get("rating")))
    if rating > 10:
        rating /= 100
    else:
        rating /= 10
    return _clamp(rating, 0, 1)


def _home_preference_weights(movies: list[dict]) -> tuple[Counter, Counter]:
    """Build lightweight preference signals from locally stored playback state only."""
    category_weights: Counter = Counter()
    genre_weights: Counter = Counter()
    for movie in movies:
        if not _is_watched_movie(movie):
            continue

        watched_seconds = max(_playback_watch_seconds(movie), _playback_current_time(movie))
        # A short preview still says something, while long watches do not
        # overwhelm every other signal.
        weight = min(1.0, 0.25 + math.log1p(watched_seconds) / math.log1p(60 * 60))
        if _playback_percent(movie) >= 90:
            weight *= 0.8

        category_weights[_primary_browse_category(movie)] += weight
        for genre in _as_list(movie.get("genres")):
            genre_weights[str(genre).strip().casefold()] += weight
    return category_weights, genre_weights


def _daily_recommendation_tiebreaker(movie: dict, day_key: str) -> str:
    """Keep ordering stable during one day while allowing equal candidates to rotate later."""
    identity = str(movie.get("id") or movie.get("title") or "")
    return hashlib.sha256(f"{day_key}:{identity}".encode("utf-8")).hexdigest()


def _home_recommendation_entry(
    movie: dict,
    category_weights: Counter,
    genre_weights: Counter,
    now_timestamp: float,
    day_key: str,
) -> dict:
    """Score a collapsed library item with transparent, local-only signals."""
    playback = _playback(movie)
    progress = _playback_percent(movie)
    is_resume = 0 < progress < 90 or (
        _playback_current_time(movie) > 0 and progress < 90
    )
    rating = _normalized_rating(movie)
    vote_count = max(0.0, _safe_float(movie.get("vote_count")))

    # ``added_at`` is the first time the scanner saw an item.  Older library
    # entries use their last-known update time as a safe compatibility fallback.
    added_timestamp = _home_timestamp(movie.get("added_at") or movie.get("updated_at"))
    added_age_days = max(0.0, (now_timestamp - added_timestamp) / 86400) if added_timestamp else 9999.0
    freshness = max(0.0, 1.0 - min(added_age_days / 120, 1.0))

    category = _primary_browse_category(movie)
    max_category_weight = max(category_weights.values(), default=0)
    category_affinity = (
        category_weights.get(category, 0.0) / max_category_weight
        if max_category_weight else 0.0
    )
    max_genre_weight = max(genre_weights.values(), default=0)
    genre_affinity = 0.0
    if max_genre_weight:
        genre_affinity = max(
            (genre_weights.get(str(genre).strip().casefold(), 0.0) / max_genre_weight
             for genre in _as_list(movie.get("genres"))),
            default=0.0,
        )

    score = 0.0
    # The continuation row already owns resumable titles, so retain at most
    # one there later; it is helpful but must not turn the hero into six copies
    # of "continue watching".
    if is_resume:
        score += 42
    if movie.get("is_favorite"):
        score += 24
    score += rating * 30
    if vote_count:
        score += min(6.0, math.log1p(vote_count) / math.log1p(1000) * 6.0)
    score += freshness * 22
    score += category_affinity * 15
    score += genre_affinity * 7

    if is_resume:
        reason = "继续观看"
    elif movie.get("is_favorite"):
        reason = "收藏优先"
    elif rating >= 0.78:
        reason = "高分优选"
    elif freshness >= 0.45:
        reason = "最近入库"
    elif category_affinity >= 0.5 or genre_affinity >= 0.5:
        reason = "偏好推荐"
    else:
        reason = "为你推荐"

    return {
        "movie": movie,
        "score": score,
        "is_resume": is_resume,
        "reason": reason,
        "category": category,
        "daily_tiebreaker": _daily_recommendation_tiebreaker(movie, day_key),
    }


def _build_home_hero(movies: list[dict], limit: int = 5, now: Optional[datetime] = None) -> list[dict]:
    """Choose diverse hero recommendations from local library metadata and history.

    The function deliberately does not make network calls or use random state:
    one library state yields the same carousel for the whole calendar day.
    """
    if limit <= 0:
        return []

    now = now or datetime.now()
    now_timestamp = now.timestamp()
    day_key = now.date().isoformat()
    category_weights, genre_weights = _home_preference_weights(movies)
    raw_entries = [
        _home_recommendation_entry(movie, category_weights, genre_weights, now_timestamp, day_key)
        for movie in movies
    ]
    grouped_entries: dict[str, list[dict]] = {}
    for entry in raw_entries:
        grouped_entries.setdefault(_home_group_key(entry["movie"]), []).append(entry)

    # Score actual resources before collapsing them.  That way a progress
    # record on Season 2 or an SDR version wins over the default Season 1/
    # Dolby representative, while each logical title still appears only once.
    entries = []
    for group in grouped_entries.values():
        group.sort(key=lambda entry: (
            -entry["score"],
            entry["daily_tiebreaker"],
            str(entry["movie"].get("id") or ""),
        ))
        chosen = group[0]
        visual_entries = [
            entry for entry in group
            if str(entry["movie"].get("backdrop_url") or entry["movie"].get("cover_url") or "").strip()
        ]
        if not visual_entries:
            continue

        # A season/version can have a real resume point without its own
        # artwork.  Borrow the group's artwork only for presentation; retain
        # the chosen resource ID so play always opens the correct season/version.
        visual_entries.sort(key=lambda entry: (
            -entry["score"],
            entry["daily_tiebreaker"],
        ))
        preferred_entry = next(
            (entry for entry in group if _as_bool(entry["movie"].get("home_display"))),
            None,
        )
        presentation_movie = dict((preferred_entry or chosen)["movie"])
        artwork_movie = visual_entries[0]["movie"]
        if not presentation_movie.get("backdrop_url"):
            presentation_movie["backdrop_url"] = artwork_movie.get("backdrop_url") or artwork_movie.get("cover_url") or ""
        if not presentation_movie.get("cover_url"):
            presentation_movie["cover_url"] = artwork_movie.get("cover_url") or artwork_movie.get("backdrop_url") or ""
        chosen = {**chosen, "presentation_movie": presentation_movie}
        entries.append(chosen)

    entries.sort(key=lambda entry: (
        -entry["score"],
        entry["daily_tiebreaker"],
        str(entry["movie"].get("title") or "").casefold(),
        str(entry["movie"].get("id") or ""),
    ))

    selected: list[dict] = []
    category_counts: Counter = Counter()
    resume_count = 0
    category_count = len({entry["category"] for entry in entries})
    max_per_category = 2 if category_count > 1 else limit

    # First pass produces a varied showcase: one resumable title at most and
    # no category monopolizes all slides when alternatives exist.
    for entry in entries:
        if len(selected) >= limit:
            break
        if entry["is_resume"] and resume_count >= 1:
            continue
        if category_counts[entry["category"]] >= max_per_category:
            continue
        selected.append(entry)
        category_counts[entry["category"]] += 1
        resume_count += int(entry["is_resume"])

    # Sparse libraries should still get all available visual items.  Relax
    # diversity constraints in a deterministic order rather than returning a
    # short, seemingly broken carousel.
    for entry in entries:
        if len(selected) >= limit:
            break
        if entry in selected:
            continue
        if entry["is_resume"] and resume_count >= 1:
            continue
        selected.append(entry)
        resume_count += int(entry["is_resume"])
    for entry in entries:
        if len(selected) >= limit:
            break
        if entry not in selected:
            selected.append(entry)

    hero = []
    for entry in selected:
        api_item = movie_to_api_format(entry.get("presentation_movie") or entry["movie"])
        hero.append({
            "id": api_item["id"],
            "title": api_item["title"],
            "category": api_item["category"],
            "year": api_item["year"],
            "releaseDate": api_item.get("releaseDate", ""),
            "sourceType": api_item["sourceType"],
            "sourceName": api_item["sourceName"],
            "durationText": api_item["durationText"],
            "backdropUrl": api_item.get("backdropUrl", api_item.get("coverUrl", "")),
            "tags": api_item["tags"],
            "description": api_item.get("description", ""),
            "rating": api_item.get("score", 0),
            "recommendationReason": entry["reason"],
            "isResume": entry["is_resume"],
        })
    return hero


def build_home_data(movies: list, category: Optional[str], limit: int, now: Optional[datetime] = None) -> dict:
    """Build homepage data with a locally ranked, stable daily carousel."""
    if category and category != "all":
        target_category = str(category).lower()
        movies = [
            m for m in movies
            if target_category in _api_categories(m)
        ]
    hero = _build_home_hero(movies, limit=5, now=now)
    movies = _collapse_home_movies(movies)

    stats = compute_home_stats(movies)
    items = [movie_to_api_format(m) for m in movies[:limit]]

    return {
        "stats": stats,
        "hero": hero,
        "items": items,
    }
