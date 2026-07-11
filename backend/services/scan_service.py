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
except ImportError:
    from config import AppConfig
    from core.filename_parser import merge_series_videos
    from core.local_scanner import LocalScanner
    from core.webdav_client import VIDEO_EXTENSIONS, WebDAVClient
from . import library_service, source_service

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
    "rating",
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
            "current": "",
            "processed": 0,
            "total": 0,
            "error": "",
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
            "current": "",
            "processed": 0,
            "total": 0,
            "error": "",
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

    _set_status(source_id, stage="scan", current=source.get("name", ""))
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

    _set_status(source_id, stage="parse", total=len(files), processed=0)

    previous_library = library_service.load_library()
    previous_by_id = {
        str(movie.get("id") or ""): movie
        for movie in previous_library
        if movie.get("source_id") == source_id and str(movie.get("id") or "")
    }
    movies = merge_series_videos(files, source.get("name", ""))
    enriched = []
    auto_scrape = _auto_scrape_enabled()
    scraper = None
    if auto_scrape:
        _set_status(source_id, stage="scrape", processed=0, total=len(movies))
        scraper = _create_scraper()
        if scraper is None:
            auto_scrape = False
    for index, movie in enumerate(movies, start=1):
        if _is_cancelled(source_id):
            break
        _set_status(
            source_id,
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
        if previous_item and previous_item.get("metadata_locked"):
            _copy_locked_metadata(item, previous_item)
        if index == 1 or not auto_scrape:
            logger.info("-" * 48)
        _log_detected_movie(item)
        if auto_scrape and not item.get("metadata_locked"):
            _scrape_metadata(source_id, [item], scraper=scraper)
        elif item.get("metadata_locked"):
            logger.info("已锁定自定义资料，跳过自动刮削：%s", item.get("display_title") or item.get("title", ""))
        enriched.append(item)

    existing = [m for m in previous_library if m.get("source_id") != source_id]
    library_service.save_library(existing + enriched)

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
            error="",
            finishedAt=_now_iso(),
        )


def _copy_locked_metadata(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in LOCKED_METADATA_FIELDS:
        if key in source:
            target[key] = source[key]


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


def _scrape_metadata(source_id: str, movies: list[dict[str, Any]], scraper: Any | None = None) -> None:
    if scraper is None:
        scraper = _create_scraper()
    if scraper is None:
        return

    for index, movie in enumerate(movies, start=1):
        _set_status(source_id, current=movie.get("title", ""), processed=index)
        try:
            scrape_title = (
                str(movie.get("series_title") or "").strip()
                or str(movie.get("title") or "").strip()
                or _clean_log_title(movie)
                or str(movie.get("search_title") or "").strip()
            )
            
            query_names = _scrape_query_names(movie)
            preferred_source = _preferred_scrape_source(scraper, movie)
            logger.info("开始刮削：选择%s源 搜索名：%s", preferred_source, " ，".join(query_names))
            meta = scraper.scrape(
                scrape_title,
                category=movie.get("category", "电影"),
                year=int(movie.get("year_hint") or 0),
                season=int(movie.get("season") or 1),
                is_series=bool(movie.get("is_series")),
                season_title=movie.get("season_title", ""),
                aliases=movie.get("aliases", []),
                origin_countries=movie.get("origin_countries", []),
                chapter_name=movie.get("chapter_name", ""),
                part=movie.get("part"),
            )
            if meta.get("title") or meta.get("cover_url"):
                logger.info("搜索到  %s下载元数据和封面", meta.get("title") or scrape_title)
                logger.info("刮削成功")
            else:
                logger.info("未搜索到  %s", scrape_title)
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
            
            media_type = str(meta.get("tmdb_media_type") or "").strip().lower()
            genres = meta.get("genres") or []
            if media_type:
                if media_type == "tv":
                    has_animation = any(
                        str(g).lower() in {"animation", "动画", "アニメ"}
                        for g in genres
                    )
                    has_anime_keyword = any(
                        str(g).lower() in {"anime", "动漫"}
                        for g in genres
                    )
                    if has_animation or has_anime_keyword:
                        movie["category"] = "动漫"
                    else:
                        movie["category"] = "电视剧"
                    movie["is_series"] = True
                elif media_type == "movie":
                    has_animation = any(
                        str(g).lower() in {"animation", "动画", "アニメ"}
                        for g in genres
                    )
                    if has_animation:
                        movie["category"] = "动漫"
                    else:
                        movie["category"] = "电影"
                    movie["is_series"] = False
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
