# -*- coding: utf-8 -*-
"""Background media scanning service."""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime
from typing import Any, Optional

try:
    from backend.config import AppConfig
    from backend.core.filename_parser import merge_series_videos
    from backend.core.local_scanner import LocalScanner
    from backend.core.webdav_client import VIDEO_EXTENSIONS, WebDAVClient
    from backend.core import llm_scrape
except ImportError:
    from config import AppConfig
    from core.filename_parser import merge_series_videos
    from core.local_scanner import LocalScanner
    from core.webdav_client import VIDEO_EXTENSIONS, WebDAVClient
    from core import llm_scrape
from . import library_service, source_service, db_service

logger = logging.getLogger(__name__)

_status_lock = threading.Lock()
_scan_threads: dict[str, threading.Thread] = {}
_statuses: dict[str, dict[str, Any]] = {}
_cancel_events: dict[str, threading.Event] = {}
_source_probe_logged = False

LOCKED_METADATA_FIELDS = (
    "metadata_locked",
    "metadata_title",
    "display_title",
    "intro",
    "year",
    "release_date",
    "release_date_checked",
    "rating",
    "rating_checked",
    "cover_url",
    "backdrop_url",
    "tags",
    "genres",
    "countries",
    "languages",
    "duration",
    "metadata_source",
    "original_title",
    "tmdb_id",
    "tmdb_media_type",
    "douban_url",
    "vote_count",
)

# These values come from a metadata provider (or a manual metadata submission),
# rather than from the file scan.  Keep this list deliberately separate from
# episodes/files/file_path: a rescan must always replace those scan-derived
# values so that newly added episodes are visible immediately.
SCRAPED_METADATA_FIELDS = (
    "metadata_locked",
    "metadata_title",
    "display_title",
    "intro",
    "year",
    "release_date",
    "release_date_checked",
    "rating",
    "rating_checked",
    "cover_url",
    "backdrop_url",
    "tags",
    "genres",
    "countries",
    "languages",
    "duration",
    "metadata_source",
    "original_title",
    "tmdb_id",
    "tmdb_media_type",
    "douban_url",
    "vote_count",
)

# Rescanning should not discard user state just because the logical item was
# rebuilt from the file list.
PERSISTED_USER_STATE_FIELDS = (
    "is_favorite",
    "playback",
    "home_display",
)

_METADATA_EVIDENCE_FIELDS = (
    "metadata_title",
    "cover_url",
    "backdrop_url",
    "intro",
    "tmdb_id",
    "douban_url",
    "original_title",
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_scraper_source_availability(force: bool = False) -> None:
    global _source_probe_logged
    if _source_probe_logged and not force:
        return
    _source_probe_logged = True

    config = AppConfig()
    config.load_config()
    douban_ok, douban_reason = _probe_douban(config)
    tmdb_ok, tmdb_reason = _probe_tmdb(config)
    logger.info(
        "刮削源检测：豆瓣%s（%s）；TMDB%s（%s）",
        "可用" if douban_ok else "不可用",
        douban_reason,
        "可用" if tmdb_ok else "不可用",
        tmdb_reason,
    )


def _probe_douban(config: AppConfig) -> tuple[bool, str]:
    cookie = str(getattr(config, "DOUBAN_COOKIE", "") or "").strip()
    if not cookie:
        return False, "未配置 Cookie"
    try:
        import requests

        session = requests.Session()
        session.trust_env = False
        resp = session.get(
            "https://movie.douban.com/",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        if resp.status_code < 500:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


def _probe_tmdb(config: AppConfig) -> tuple[bool, str]:
    api_key = str(getattr(config, "TMDB_API_KEY", "") or "").strip()
    if not api_key:
        return False, "未配置 API Key"
    try:
        import requests

        base = str(getattr(config, "TMDB_API_BASE", "") or "https://api.themoviedb.org/3").rstrip("/")
        session = requests.Session()
        session.trust_env = False
        resp = session.get(f"{base}/configuration", params={"api_key": api_key}, timeout=5)
        if resp.status_code == 200:
            return True, "API 正常"
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


def get_status(source_id: str) -> dict[str, Any]:
    with _status_lock:
        return dict(_statuses.get(source_id, {
            "scanning": False,
            "stage": "idle",
            "activity": "",
            "current": "",
            "processed": 0,
            "total": 0,
            "error": "",
            "metadataReused": 0,
            "metadataScraped": 0,
            "episodesUpdated": 0,
            "itemsPublished": 0,
        }))


def cancel_scan(source_id: str) -> bool:
    with _status_lock:
        event = _cancel_events.get(source_id)
        if not event:
            return False
        event.set()
        return True


def start_background_scan(source_id: str) -> dict[str, Any]:
    with _status_lock:
        thread = _scan_threads.get(source_id)
        if thread and thread.is_alive():
            return dict(_statuses[source_id])

        _statuses[source_id] = {
            "scanning": True,
            "stage": "queued",
            "activity": "正在排队",
            "current": "",
            "processed": 0,
            "total": 0,
            "error": "",
            "metadataReused": 0,
            "metadataScraped": 0,
            "episodesUpdated": 0,
            "itemsPublished": 0,
            "startedAt": _now_iso(),
            "finishedAt": "",
        }

        _cancel_events[source_id] = threading.Event()
        thread = threading.Thread(target=_scan_worker, args=(source_id,), daemon=True)
        _scan_threads[source_id] = thread
        thread.start()
        return dict(_statuses[source_id])


def _set_status(source_id: str, **updates: Any) -> None:
    with _status_lock:
        current = _statuses.setdefault(source_id, {})
        current.update(updates)


def _is_cancelled(source_id: str) -> bool:
    event = _cancel_events.get(source_id)
    return event.is_set() if event else False


def _scan_worker(source_id: str) -> None:
    try:
        _scan_source(source_id)
    except Exception as exc:
        logger.exception("Scan failed for source %s", source_id)
        _set_status(
            source_id,
            scanning=False,
            stage="error",
            error=str(exc),
            finishedAt=_now_iso(),
        )
        _update_source_after_scan(source_id, scan_error=str(exc))
    finally:
        with _status_lock:
            thread = _scan_threads.get(source_id)
            if thread and not thread.is_alive():
                _scan_threads.pop(source_id, None)
            _cancel_events.pop(source_id, None)


def _scan_source(source_id: str) -> None:
    sources = source_service.load_sources()
    source = next((item for item in sources if item.get("id") == source_id), None)
    if not source:
        raise ValueError("Data source not found")

    _set_status(source_id, stage="scan", activity="正在读取文件", current=source.get("name", ""))
    library_service.remove_source_movies_outside_paths(
        source_id,
        _source_scan_roots(source),
    )
    files = _collect_video_files(source)
    if _is_cancelled(source_id):
        _set_status(
            source_id,
            scanning=False,
            stage="cancelled",
            current="",
            processed=0,
            total=0,
            error="扫描已取消",
            finishedAt=_now_iso(),
        )
        return

    _set_status(source_id, stage="parse", activity="正在识别影视", total=len(files), processed=0)

    previous_library = library_service.load_library()
    previous_by_id = {
        str(movie.get("id") or ""): movie
        for movie in previous_library
        if movie.get("source_id") == source_id and str(movie.get("id") or "")
    }
    previous_by_metadata_key: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for movie in previous_library:
        if movie.get("source_id") != source_id:
            continue
        metadata_key = _metadata_cache_key(movie)
        if metadata_key:
            previous_by_metadata_key.setdefault(metadata_key, []).append(movie)

    movies = merge_series_videos(files, source.get("name", ""))
    enriched = []
    auto_scrape = _auto_scrape_enabled()
    scraper = None
    metadata_reused = 0
    metadata_scraped = 0
    episodes_updated = 0
    items_published = 0
    for index, movie in enumerate(movies, start=1):
        if _is_cancelled(source_id):
            break
        _set_status(
            source_id,
            stage="parse",
            activity="正在整理影视",
            current=movie.get("title", ""),
            processed=index,
            total=len(movies),
        )
        item = dict(movie)
        item["source_id"] = source_id
        item["source_name"] = source.get("name", "")
        item["source_type"] = source.get("type", "")
        item["updated_at"] = _now_iso()
        if item.get("file_path") and not item.get("path"):
            item["path"] = item["file_path"]
        previous_item = previous_by_id.get(str(item.get("id") or ""))

        # A normal episode update keeps the logical item ID.  Fall back to a
        # conservative metadata key for a one-file movie that later becomes
        # an S1 series (and consequently gains an S1 suffix in its ID).
        if previous_item is None:
            candidates = previous_by_metadata_key.get(_metadata_cache_key(item), [])
            if len(candidates) == 1:
                previous_item = candidates[0]

        # ``updated_at`` changes on every scan, while ``added_at`` records
        # when this logical resource first entered the library.  Keep the old
        # scan timestamp as a migration fallback for libraries created before
        # this field existed.
        if previous_item:
            item["added_at"] = (
                previous_item.get("added_at")
                or previous_item.get("updated_at")
                or item["updated_at"]
            )
        else:
            item["added_at"] = item["updated_at"]

        metadata_reused_for_item = False
        metadata_needs_date_refresh = False
        metadata_needs_rating_refresh = False
        if previous_item:
            _copy_persisted_user_state(item, previous_item)
            if _episode_signature(item) != _episode_signature(previous_item):
                episodes_updated += 1
            if previous_item.get("metadata_locked"):
                _copy_locked_metadata(item, previous_item)
                metadata_reused_for_item = True
            elif _has_reusable_metadata(previous_item):
                _copy_scraped_metadata(item, previous_item)
                metadata_reused_for_item = True
                metadata_needs_date_refresh = not previous_item.get("release_date_checked")
                metadata_needs_rating_refresh = not previous_item.get("rating_checked")

        if metadata_reused_for_item:
            metadata_reused += 1

        if index == 1:
            logger.info("-" * 48)
        _log_detected_movie(item)
        # New/failed entries are scraped lazily. Libraries created before
        # complete release dates and ratings were stored reuse their current
        # metadata, then receive one additive enrichment without losing
        # artwork when a remote provider is unavailable.
        if auto_scrape and (
            not metadata_reused_for_item
            or metadata_needs_date_refresh
            or metadata_needs_rating_refresh
        ):
            if scraper is None:
                scraper = _create_scraper()
                if scraper is None:
                    auto_scrape = False
            if auto_scrape and scraper is not None:
                _set_status(source_id, stage="scrape", activity="正在准备刮削")
                _scrape_metadata(
                    source_id,
                    [item],
                    scraper=scraper,
                    progress_index=index,
                    progress_total=len(movies),
                )
                metadata_scraped += 1
        elif item.get("metadata_locked"):
            logger.info("已锁定自定义资料，跳过自动刮削：%s", item.get("display_title") or item.get("title", ""))
        _set_status(
            source_id,
            stage="parse",
            activity="正在整理影视",
            current=item.get("title", ""),
            processed=index,
            total=len(movies),
            metadataReused=metadata_reused,
            metadataScraped=metadata_scraped,
            episodesUpdated=episodes_updated,
        )
        enriched.append(item)
        # Persist every completed entry as soon as its scrape finishes. The
        # home page can then refresh from real library data before this source
        # has finished processing its remaining files.
        library_service.upsert_movie(item)
        items_published += 1
        _set_status(source_id, itemsPublished=items_published)

    # Only a complete scan can establish that a previously known file has
    # disappeared. A cancelled scan retains old entries and newly published
    # cards alike.
    if not _is_cancelled(source_id):
        library_service.remove_source_movies_not_in(
            source_id,
            [str(item.get("id") or "") for item in enriched],
        )

    stats = library_service.compute_stats(enriched)
    _update_source_after_scan(source_id, stats=stats, scan_error="")

    if _is_cancelled(source_id):
        _set_status(
            source_id,
            scanning=False,
            stage="cancelled",
            current="",
            processed=len(enriched),
            total=len(movies),
            metadataReused=metadata_reused,
            metadataScraped=metadata_scraped,
            episodesUpdated=episodes_updated,
            itemsPublished=items_published,
            error="扫描已取消",
            finishedAt=_now_iso(),
        )
    else:
        _set_status(
            source_id,
            scanning=False,
            stage="done",
            current="",
            processed=len(enriched),
            total=len(enriched),
            metadataReused=metadata_reused,
            metadataScraped=metadata_scraped,
            episodesUpdated=episodes_updated,
            itemsPublished=items_published,
            error="",
            finishedAt=_now_iso(),
        )


def _copy_locked_metadata(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in LOCKED_METADATA_FIELDS:
        if key in source:
            target[key] = source[key]


def _metadata_cache_key(movie: dict[str, Any]) -> tuple[str, ...]:
    """Build a stable key for metadata reuse within a single data source."""
    title = (
        movie.get("series_title")
        or movie.get("title")
        or movie.get("name")
        or movie.get("search_title")
        or ""
    )
    normalized_title = _normalize_metadata_key(title)
    if not normalized_title:
        return ()
    return (
        normalized_title,
        _normalize_metadata_key(movie.get("year_hint") or ""),
        _normalize_metadata_key(movie.get("season") or 1),
        _normalize_metadata_key(movie.get("season_title") or ""),
        _normalize_metadata_key(movie.get("special_type") or ""),
        _normalize_metadata_key(movie.get("part") or ""),
        _normalize_metadata_key(movie.get("version_title") or ""),
    )


def _normalize_metadata_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def _episode_signature(movie: dict[str, Any]) -> tuple[str, ...]:
    """Represent the current episode list without depending on file paths."""
    episodes = movie.get("episodes")
    if not isinstance(episodes, list):
        episodes = []
    identifiers: list[str] = []
    for episode in episodes:
        if isinstance(episode, dict):
            value = episode.get("id") or episode.get("number") or episode.get("episode") or ""
        else:
            value = episode
        normalized = str(value or "").strip()
        if normalized:
            identifiers.append(normalized)
    if identifiers:
        return tuple(sorted(identifiers))
    count = movie.get("episode_count") or 0
    return (f"count:{count}",) if count else ()


def _has_reusable_metadata(movie: dict[str, Any]) -> bool:
    """Do not treat provider labels alone as a successful scrape result."""
    for key in _METADATA_EVIDENCE_FIELDS:
        value = movie.get(key)
        if isinstance(value, str):
            if value.strip():
                return True
        elif value:
            return True
    return False


def _copy_scraped_metadata(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in SCRAPED_METADATA_FIELDS:
        if key in source:
            target[key] = _copy_cached_value(source[key])


def _copy_persisted_user_state(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in PERSISTED_USER_STATE_FIELDS:
        if key in source:
            target[key] = _copy_cached_value(source[key])


def _copy_cached_value(value: Any) -> Any:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def _collect_video_files(source: dict[str, Any]) -> list[str]:
    source_type = source.get("type")
    selected_paths = _selected_paths(source)
    source_id = source.get("id", "")

    if source_type == "local":
        config = AppConfig()
        config.load_config()
        scanner = LocalScanner(max_depth=int(config.LOCAL_SCAN_MAX_DEPTH or 3))
        roots = selected_paths if selected_paths is not None else [source.get("path", "")]
        files: list[str] = []
        for root in roots:
            if _is_cancelled(source_id):
                break
            _set_status(source_id, current=root)
            files.extend(scanner.scan_directory(root))
        return _dedupe(files)

    if source_type == "webdav":
        config = AppConfig()
        config.load_config()
        client = WebDAVClient(
            host=source.get("path") or _build_webdav_base_url(source),
            username=source.get("username", ""),
            password=source.get("password", ""),
        )
        # 仅扫描用户保存的目录；不要用父目录替换用户的精确选择。
        roots = selected_paths if selected_paths is not None else ["/"]
        files = []
        for root in roots:
            if _is_cancelled(source_id):
                break
            def report_progress(directories: int, found: int, current_path: str) -> None:
                _set_status(
                    source_id,
                    current=current_path,
                    directoriesScanned=directories,
                    filesFound=len(files) + found,
                )

            files.extend(
                client.list_files_recursive(
                    root,
                    max_depth=int(config.SCAN_MAX_DEPTH or 2),
                    progress_cb=report_progress,
                    should_cancel=lambda: _is_cancelled(source_id),
                )
            )
        return _dedupe(files)

    if source_type == "openlist":
        config = AppConfig()
        config.load_config()
        roots = selected_paths if selected_paths is not None else [source.get("mount_path", "/")]
        return _scan_openlist_roots(roots, source_id)

    return []


def _scan_openlist_roots(roots: list[str], source_id: str = "") -> list[str]:
    try:
        from backend.config import AppConfig
        from backend.core.openlist_client import openlist_client
        from backend.core.openlist_manager import openlist_manager
    except ImportError:
        from config import AppConfig
        from core.openlist_client import openlist_client
        from core.openlist_manager import openlist_manager

    config = AppConfig()
    config.load_config()
    status = openlist_manager.get_status()
    if status.get("status") != "running":
        raise RuntimeError("Built-in OpenList is not running")

    password = config.OPENLIST_ADMIN_PASSWORD
    if not password:
        raise RuntimeError("OpenList admin password is missing")

    base_url = status.get("base_url") or f"http://127.0.0.1:{status.get('port', 5244)}"
    openlist_client.set_base_url(base_url)
    openlist_client.login(password)

    max_depth = int(config.SCAN_MAX_DEPTH or 2)
    files: list[str] = []
    seen_dirs: set[str] = set()
    queue: list[tuple[str, int]] = [(root if root.startswith("/") else f"/{root}", 0) for root in roots if root]

    while queue:
        if _is_cancelled(source_id):
            break
        path, depth = queue.pop(0)
        if path in seen_dirs:
            continue
        seen_dirs.add(path)
        try:
            result = openlist_client.list_files(password, path, page=1, per_page=0)
        except Exception as exc:
            message = str(exc)
            if "object not found" in message.lower() or "failed get dir" in message.lower():
                logger.warning("Skip missing OpenList scan path: %s (%s)", path, message)
                continue
            raise
        content = result.get("data", {}).get("content", []) if result.get("code") == 200 else []

        for entry in content or []:
            entry_path = _openlist_entry_path(path, entry)
            if _openlist_is_dir(entry):
                if depth < max_depth:
                    queue.append((entry_path, depth + 1))
                continue
            if os.path.splitext(entry_path)[1].lower() in VIDEO_EXTENSIONS:
                files.append(entry_path)

    return _dedupe(files)


def _openlist_is_dir(entry: dict[str, Any]) -> bool:
    value = str(entry.get("type", "")).lower()
    return bool(entry.get("is_dir") or entry.get("isDir") or value in {"folder", "directory", "dir"})


def _openlist_entry_path(parent: str, entry: dict[str, Any]) -> str:
    path = str(entry.get("path") or entry.get("full_path") or "").strip()
    if path.startswith("/"):
        return path
    name = str(entry.get("name") or "").strip()
    base = parent.rstrip("/") or "/"
    return f"{base}/{name}".replace("//", "/")


def _selected_paths(source: dict[str, Any]) -> Optional[list[str]]:
    if "selected_paths" not in source:
        return None
    paths = source["selected_paths"]
    if isinstance(paths, list):
        return [str(path).strip() for path in paths if str(path).strip()]
    if isinstance(paths, str):
        return [part.strip() for part in paths.split(",") if part.strip()]
    return []


def _source_scan_roots(source: dict[str, Any]) -> list[str]:
    selected_paths = _selected_paths(source)
    if selected_paths is not None:
        return selected_paths
    if source.get("type") == "local":
        return [str(source.get("path") or "")]
    if source.get("type") == "openlist":
        return [str(source.get("mount_path") or "/")]
    return ["/"]


def _build_webdav_base_url(source: dict[str, Any]) -> str:
    host = str(source.get("host") or "").strip()
    protocol = str(source.get("protocol") or "http").strip() or "http"
    port = str(source.get("port") or "").strip()
    if not host:
        return ""
    base_url = host if host.startswith(("http://", "https://")) else f"{protocol}://{host}"
    if port and ":" not in base_url.split("://", 1)[-1]:
        base_url = f"{base_url}:{port}"
    return base_url


def _auto_scrape_enabled() -> bool:
    config = AppConfig()
    config.load_config()
    return bool(config.ENABLE_AUTO_SCRAPE)


def _clean_log_title(movie: dict[str, Any]) -> str:
    title = str(movie.get("display_title") or movie.get("title") or movie.get("name") or "").strip()
    title = re.sub(r"\s*（第[0-9一二三四五六七八九十]+季）\s*$", "", title)
    title = re.sub(r"\s*\(Season\s+\d+\)\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*Part\s+(\d+)\s*$", r" #\1", title, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", title).strip()


def _season_log_value(movie: dict[str, Any]) -> str:
    special_type = str(movie.get("special_type") or "").strip()
    season_title = str(movie.get("season_title") or "").strip()
    if special_type and not movie.get("part"):
        return "番外"
    if any(word in season_title for word in ("番外", "特别", "OVA", "SP")):
        return "番外"
    return str(int(movie.get("season") or 1))


def _bool_cn(value: bool) -> str:
    return "是" if value else "否"


def _episode_count(movie: dict[str, Any]) -> int:
    episodes = movie.get("episodes")
    if isinstance(episodes, list) and episodes:
        return len(episodes)
    return int(movie.get("episode_count") or 1)


def _log_detected_movie(movie: dict[str, Any]) -> None:
    title = _clean_log_title(movie)
    category = str(movie.get("category") or "电影")
    episode_count = _episode_count(movie)
    season_value = _season_log_value(movie)
    part = movie.get("part")
    version = str(movie.get("version_title") or "").strip()
    is_multi_chapter = bool(part)
    is_multi_version = bool(version)
    message = (
        f"扫描到：《{title}》类型：{category} 集数：{episode_count} "
        f" 季数：{season_value} 是否是多章节：{_bool_cn(is_multi_chapter)}"
    )
    if is_multi_chapter:
        message += f"  章节部分：{part}"
    message += f" 是否是多版本：{_bool_cn(is_multi_version)}"
    if is_multi_version:
        message += f" 版本：{version}"
    logger.info(message)


def _cn_num(value: int) -> str:
    numbers = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    if 0 <= value <= 10:
        return numbers[value]
    if value < 20:
        return f"十{numbers[value - 10]}"
    if value < 100:
        high, low = divmod(value, 10)
        return f"{numbers[high]}十{numbers[low] if low else ''}"
    return str(value)


def _scrape_query_names(movie: dict[str, Any]) -> list[str]:
    title = str(movie.get("series_title") or movie.get("title") or movie.get("name") or "").strip()
    if not title:
        title = _clean_log_title(movie)
    base_title = re.sub(r"\s*第[一二三四五六七八九十\d]+季\s*$", "", title).strip()
    queries = []
    season_title = str(movie.get("season_title") or "").strip()
    special_type = str(movie.get("special_type") or "").strip()
    chapter_name = str(movie.get("chapter_name") or "").strip()
    part = movie.get("part")
    base = base_title or title
    
    if chapter_name:
        if part and part > 0:
            queries.append(f"{base} {chapter_name} #{part}")
            queries.append(f"{base} {chapter_name}{part}")
            queries.append(f"{base} {chapter_name} Part{part}")
        queries.append(f"{base} {chapter_name}")
    elif season_title and part and part > 0:
        queries.append(f"{base} {season_title}{part}")
        queries.append(f"{base} {season_title} Part{part}")
    elif season_title and season_title not in {base_title, title}:
        queries.append(f"{base} {season_title}")

    if season_title and season_title not in {base_title, title}:
        queries.append(f"{base} {season_title}")
    
    if special_type and special_type not in season_title and special_type != chapter_name:
        queries.append(f"{base} {special_type}")
    
    season_value = _season_log_value(movie)
    if season_value == "番外":
        queries.append(f"{base} 番外")
    else:
        season = int(movie.get("season") or 1)
        if season > 1:
            if base_title and base_title != title:
                queries.append(title)
            else:
                queries.append(f"{title} 第{_cn_num(season)}季")
    queries.append(base)
    
    deduped = list(dict.fromkeys([query for query in queries if query]))
    return deduped[:1] if deduped else []


def _preferred_scrape_source(scraper: Any, movie: dict[str, Any]) -> str:
    try:
        order = scraper._scrape_source_order(movie.get("category", "电影"))
        if order:
            return str(order[0])
    except Exception:
        pass
    return "auto"


def _fallback_to_pool(title: str, year_hint: int, is_series: bool) -> dict[str, Any] | None:
    """TMDB 刮削失败时，用本地 metadata_pool 按片名+年份兜底匹配。

    返回与 scraper.scrape 兼容的 meta dict，未命中返回 None。
    """
    if not title:
        return None
    try:
        media_type = "tv" if is_series else "movie"
        # 用 query_pool 的关键词搜索（FTS5），取同 media_type 且年份最接近的
        rows = db_service.query_pool({"q": title, "media_type": media_type, "page": 1, "per_page": 10})
        if not rows:
            return None
        best = None
        best_score = -1.0
        for row in rows:
            r_title = str(row.get("title") or "")
            if not r_title:
                continue
            # 标题包含匹配度
            title_lower = title.lower()
            r_title_lower = r_title.lower()
            title_match = 1.0 if title_lower == r_title_lower else (
                0.8 if title_lower in r_title_lower or r_title_lower in title_lower else 0.3
            )
            # 年份接近度
            r_year = int(row.get("year") or 0)
            year_diff = abs(r_year - year_hint) if year_hint and r_year else 0
            year_score = max(0.0, 1.0 - year_diff / 10.0) if year_hint else 0.5
            score = title_match * 0.7 + year_score * 0.3
            if score > best_score:
                best_score = score
                best = row
        if not best or best_score < 0.4:
            return None
        poster = best.get("poster_path") or ""
        backdrop = best.get("backdrop_path") or ""
        return {
            "title": best.get("title"),
            "cover_url": f"https://image.tmdb.org/t/p/w342{poster}" if poster else "",
            "backdrop_url": f"https://image.tmdb.org/t/p/w780{backdrop}" if backdrop else "",
            "description": best.get("overview") or "",
            "score": best.get("vote_average"),
            "year": best.get("year"),
            "genres": [g.strip() for g in str(best.get("genres") or "").split(",") if g.strip()],
            "countries": [c.strip() for c in str(best.get("origin_country") or "").split(",") if c.strip()],
            "original_title": best.get("original_title") or "",
            "tmdb_media_type": media_type,
            "metadata_source": "metadata_pool",
            "duration": best.get("runtime"),
        }
    except Exception as exc:
        logger.debug("metadata_pool 兜底跳过: %s", exc)
        return None


def _create_scraper() -> Any | None:
    try:
        try:
            from backend.core.cover_scraper import CoverScraper
        except ImportError:
            from core.cover_scraper import CoverScraper
        return CoverScraper()
    except Exception as exc:
        logger.warning("Metadata scraper is unavailable: %s", exc)
        return None


def _scrape_metadata(
    source_id: str,
    movies: list[dict[str, Any]],
    scraper: Any | None = None,
    progress_index: int | None = None,
    progress_total: int | None = None,
) -> None:
    if scraper is None:
        scraper = _create_scraper()
    if scraper is None:
        return

    provider_labels = {"anibk": "AniBK", "douban": "豆瓣", "tmdb": "TMDB"}
    for index, movie in enumerate(movies, start=1):
        processed = progress_index if progress_index is not None else index
        status_updates = {
            "stage": "scrape",
            "activity": "正在准备元数据",
            "current": movie.get("title", ""),
            "processed": processed,
        }
        if progress_total is not None:
            status_updates["total"] = progress_total
        _set_status(source_id, **status_updates)
        try:
            scrape_title = (
                str(movie.get("series_title") or "").strip()
                or str(movie.get("title") or "").strip()
                or _clean_log_title(movie)
                or str(movie.get("search_title") or "").strip()
            )
            
            query_names = _scrape_query_names(movie)
            # G1：规则解析置信度低时，由大模型识别规范片名（未配置/失败静默回退规则标题）。
            # 已锁定元数据的条目标题已规范化，无需再识别。
            scrape_aliases = list(movie.get("aliases") or [])
            llm_match = None
            if not movie.get("metadata_locked"):
                try:
                    llm_match = llm_scrape.enhance_scrape_title(movie)
                except Exception as exc:
                    logger.debug("AI 刮削增强跳过: %s", exc)
            if llm_match:
                rule_title = scrape_title
                scrape_title = llm_match["title"]
                original_title = str(llm_match.get("original_title") or "").strip()
                if original_title and original_title not in scrape_aliases:
                    scrape_aliases.append(original_title)
                # 记录 AI 修正痕迹，供前端刮削日志/详情展示，证明 AI 真实参与
                if rule_title and llm_match.get("title") and rule_title != llm_match["title"]:
                    movie["ai_scrape_correction"] = {
                        "from": rule_title,
                        "to": llm_match["title"],
                        "confidence": llm_match.get("confidence"),
                        "at": datetime.now().isoformat(timespec="seconds"),
                    }
            preferred_source = _preferred_scrape_source(scraper, movie)
            logger.info("开始刮削：选择%s源 搜索名：%s", preferred_source, " ，".join(query_names))

            def report_provider(provider: str) -> None:
                label = provider_labels.get(str(provider or "").lower(), str(provider or "元数据源"))
                updates = {
                    "stage": "scrape",
                    "activity": f"正在查询 {label}",
                    "current": movie.get("title", ""),
                    "processed": processed,
                }
                if progress_total is not None:
                    updates["total"] = progress_total
                _set_status(source_id, **updates)

            meta = scraper.scrape(
                scrape_title,
                category=movie.get("category", "电影"),
                year=int(movie.get("year_hint") or 0),
                season=int(movie.get("season") or 1),
                is_series=bool(movie.get("is_series")),
                season_title=movie.get("season_title", ""),
                aliases=scrape_aliases,
                origin_countries=movie.get("origin_countries", []),
                chapter_name=movie.get("chapter_name", ""),
                part=movie.get("part"),
                progress_callback=report_provider,
            )
            _set_status(source_id, stage="scrape", activity="正在保存元数据", current=movie.get("title", ""), processed=processed)
            if meta.get("title") or meta.get("cover_url"):
                logger.info("搜索到  %s下载元数据和封面", meta.get("title") or scrape_title)
                logger.info("刮削成功")
            else:
                logger.info("未搜索到  %s", scrape_title)
                # metadata_pool 本地兜底：TMDB 刮削失败时，用本地影视库按片名+年份匹配
                pool_meta = _fallback_to_pool(
                    scrape_title,
                    int(movie.get("year_hint") or 0),
                    bool(movie.get("is_series")),
                )
                if pool_meta:
                    logger.info("metadata_pool 兜底命中：%s", pool_meta.get("title"))
                    meta = pool_meta
            if meta.get("title"):
                movie["metadata_title"] = meta["title"]
                if not movie.get("season_title") and not movie.get("special_type"):
                    movie["title"] = meta["title"]
            if meta.get("cover_url"):
                movie["cover_url"] = meta["cover_url"]
            if meta.get("backdrop_url"):
                movie["backdrop_url"] = meta["backdrop_url"]
            if meta.get("description"):
                movie["intro"] = meta["description"]
            if meta.get("score"):
                movie["rating"] = meta["score"]
            if meta.get("tags"):
                movie["tags"] = meta["tags"]
            if meta.get("year"):
                movie["year"] = meta["year"]
            if meta.get("release_date"):
                movie["release_date"] = meta["release_date"]
            if meta.get("duration"):
                movie["duration"] = meta["duration"]
            for key in (
                "genres",
                "countries",
                "languages",
                "metadata_source",
                "original_title",
                "tmdb_id",
                "tmdb_media_type",
                "douban_url",
                "vote_count",
            ):
                if meta.get(key):
                    movie[key] = meta[key]
            
            # The scanner's directory category is the primary library
            # classification.  Provider genres can be absent (notably for
            # AniBK + TMDB artwork merges), so never let incomplete metadata
            # move an /动漫 item into /电视剧.  The provider media type is still
            # useful for deciding whether the item is episodic.
            media_type = str(meta.get("tmdb_media_type") or "").strip().lower()
            if media_type == "tv":
                movie["is_series"] = True
            elif media_type == "movie":
                movie["is_series"] = False
            if meta.get("title") or meta.get("cover_url") or meta.get("description"):
                movie["release_date_checked"] = True
                movie["rating_checked"] = True
        except Exception as exc:
            logger.warning("刮削失败：%s error=%s", movie.get("title", ""), exc)
        finally:
            logger.info("-" * 48)


def _update_source_after_scan(
    source_id: str,
    stats: dict[str, Any] | None = None,
    scan_error: str | None = None,
) -> None:
    sources = source_service.load_sources()
    changed = False
    for source in sources:
        if source.get("id") != source_id:
            continue
        if stats is not None:
            source["stats"] = stats
        if scan_error is not None:
            source["scan_error"] = scan_error
        source["updated_at"] = _now_iso()
        changed = True
        break
    if changed:
        source_service.save_sources(sources)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
