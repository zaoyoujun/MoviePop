from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

from config.app_config import AppConfig
from core.local_video_library import LocalVideoLibraryManager
from core.remote_source import get_remote_provider_label, infer_remote_provider
from core.video_library import VideoLibraryManager
from utils.database import VideoCache
from utils.logger import get_logger, release_logger_handlers, reconfigure_logger

logger = get_logger()
FIRST_RUN_FLAG = AppConfig().BASE_DIR / ".first_run_complete"
LOCAL_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


class LibraryService:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.config.load_config()
        self.remote_library = VideoLibraryManager()
        self.local_library = LocalVideoLibraryManager()
        self.cache = VideoCache()

    def _manager_for(self, source: str):
        if source == "local":
            return self.local_library
        return self.remote_library

    def _source_for_path(self, movie_path: str) -> str:
        return "local" if LOCAL_PATH_RE.match(movie_path or "") else "remote"

    def _resolve_cover_path(self, cover_path: str | None) -> Path | None:
        if not cover_path:
            return None
        candidate = Path(cover_path)
        if candidate.exists():
            return candidate
        fallback = self.config.COVERS_DIR / candidate.name
        if fallback.exists():
            return fallback
        return None

    def _get_remote_source_label(self) -> str:
        provider = self.config.normalize_remote_provider(self.config.REMOTE_PROVIDER)
        return get_remote_provider_label(provider)

    def _load_raw_library(self, source: str = "remote", force_refresh: bool = False) -> list[dict[str, Any]]:
        manager = self._manager_for(source)
        return copy.deepcopy(manager.get_video_list(force_refresh=force_refresh) or [])

    def _save_raw_library(self, source: str, movies: list[dict[str, Any]]) -> None:
        manager = self._manager_for(source)
        manager._save_cache(movies)  # noqa: SLF001
        if source == "local":
            LocalVideoLibraryManager._cached_list = copy.deepcopy(movies)  # noqa: SLF001
        else:
            VideoLibraryManager._cached_list = copy.deepcopy(movies)  # noqa: SLF001

    def _decorate_movie(
        self,
        movie: dict[str, Any],
        favorite_paths: set[str] | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        item = copy.deepcopy(movie)
        item_source = source or item.get("source") or self._source_for_path(item.get("path", ""))
        item.setdefault("title", item.get("name", "未命名"))
        item.setdefault("name", item.get("title", "未命名"))
        item.setdefault("type", "视频")
        item.setdefault("year", 2024)
        item.setdefault("intro", "")
        item.setdefault("rating", 0.0)
        item.setdefault("duration", "未知")
        item.setdefault("is_series", False)
        item.setdefault("episodes", [])
        item.setdefault("episode_files", [])
        item.setdefault("path", "")
        item.setdefault("cover_path", "")

        resolved_cover = self._resolve_cover_path(item.get("cover_path"))
        item["cover_path"] = str(resolved_cover) if resolved_cover else ""
        if resolved_cover:
            try:
                version = int(resolved_cover.stat().st_mtime)
            except OSError:
                version = 0
            item["cover_url"] = f"/covers/{quote(resolved_cover.name)}?v={version}"
        else:
            item["cover_url"] = ""
        item["is_favorite"] = item.get("path", "") in (favorite_paths or set())
        item["episode_count"] = len(item.get("episode_files", []))
        item["source"] = item_source
        if item_source == "local":
            item["remote_provider"] = None
            item["source_label"] = "本地视频"
        else:
            inferred_provider = infer_remote_provider(
                item.get("path", ""),
                item.get("source_label"),
                item.get("remote_provider") or self.config.normalize_remote_provider(self.config.REMOTE_PROVIDER),
            )
            item["remote_provider"] = inferred_provider
            item["source_label"] = item.get("source_label") or get_remote_provider_label(inferred_provider)
        playback = self.cache.get_playback_progress(item.get("path", "")) or {}
        progress_value = float(playback.get("progress") or 0)
        duration_value = float(playback.get("duration") or 0)
        progress_percent = 0
        if duration_value > 0 and progress_value > 0:
            progress_percent = max(0, min(100, round((progress_value / duration_value) * 100)))
        item["playback"] = {
            "progress": progress_value,
            "duration": duration_value,
            "percent": progress_percent,
            "timestamp": int(playback.get("timestamp") or 0),
            "has_progress": progress_percent > 0,
        }
        item["tags"] = self.cache.get_movie_tags(item.get("path", ""))
        return item

    def _movie_matches_source(self, movie: dict[str, Any], source: str) -> bool:
        if source == "combined":
            return True
        return self._source_for_path(movie.get("path", "")) == source

    def _catalog_for_source(self, source: str, force_refresh: bool = False) -> list[dict[str, Any]]:
        if source == "combined":
            return self.get_library("remote", force_refresh=force_refresh) + self.get_library(
                "local", force_refresh=force_refresh,
            )
        return self.get_library(source, force_refresh=force_refresh)

    def get_library(self, source: str = "remote", force_refresh: bool = False) -> list[dict[str, Any]]:
        if source == "combined":
            return self._catalog_for_source("combined", force_refresh=force_refresh)

        custom_info = self.cache.get_all_custom_info()
        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        movies = self._load_raw_library(source=source, force_refresh=force_refresh)
        for movie in movies:
            path = movie.get("path", "")
            if path in custom_info:
                movie.update(custom_info[path])
        decorated_movies = []
        for movie in movies:
            decorated_movies.append(self._decorate_movie(movie, favorite_paths, source=source))
        return decorated_movies

    def get_movie(self, movie_path: str, source: str | None = None) -> dict[str, Any] | None:
        source_candidates = []
        if source in {"remote", "local"}:
            source_candidates.append(source)
        guessed_source = self._source_for_path(movie_path)
        source_candidates.append(guessed_source)
        source_candidates.append("local" if guessed_source == "remote" else "remote")

        checked = set()
        for current_source in source_candidates:
            if current_source in checked:
                continue
            checked.add(current_source)
            for movie in self.get_library(current_source, force_refresh=False):
                if movie.get("path") == movie_path:
                    return movie

        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        custom_info = self.cache.get_all_custom_info()
        for fallback_movie in self.cache.get_recent_play() + self.cache.get_favorites():
            if fallback_movie.get("path") == movie_path:
                fallback_copy = copy.deepcopy(fallback_movie)
                if movie_path in custom_info:
                    fallback_copy.update(custom_info[movie_path])
                return self._decorate_movie(fallback_copy, favorite_paths)
        return None

    def get_movies(
        self,
        mode: str = "all",
        source: str = "remote",
        search: str = "",
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        mode = (mode or "all").lower()
        source = (source or "remote").lower()

        if mode in ["favorite", "recent"]:
            favorite_paths = {item.get("path", ""): True for item in self.cache.get_favorites()}
            if mode == "favorite":
                source_items = [
                    item for item in self.cache.get_favorites() if self._movie_matches_source(item, source)
                ]
            else:
                source_items = [
                    item for item in self.cache.get_recent_play() if self._movie_matches_source(item, source)
                ]
            movies = []
            for item in source_items:
                path = item.get("path", "")
                movie = None
                if source == "remote" and self.remote_library._cached_list:
                    for m in self.remote_library._cached_list:
                        if m.get("path") == path:
                            movie = m
                            break
                if not movie and source in ["local", "combined"] and self.local_library._cached_list:
                    for m in self.local_library._cached_list:
                        if m.get("path") == path:
                            movie = m
                            break
                if movie:
                    movies.append(self._decorate_movie(movie, set(favorite_paths.keys()), source=source))
                else:
                    movies.append(self._decorate_movie(item, set(favorite_paths.keys())))
        else:
            catalog = self._catalog_for_source(source, force_refresh=force_refresh)
            movies = catalog

        keyword = (search or "").strip().lower()
        if keyword:
            movies = [
                movie
                for movie in movies
                if keyword in movie.get("title", "").lower()
                or keyword in movie.get("name", "").lower()
                or keyword in movie.get("intro", "").lower()
                or keyword in movie.get("type", "").lower()
                or keyword in movie.get("source_label", "").lower()
            ]
        return movies

    def refresh_library(self, source: str = "remote") -> list[dict[str, Any]]:
        return self.get_library(source=source, force_refresh=True)

    def update_library_fields(
        self,
        movie_path: str,
        updates: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        source_candidates = [source] if source in {"remote", "local"} else [self._source_for_path(movie_path)]
        source_candidates.append("local" if source_candidates[0] == "remote" else "remote")

        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        checked = set()
        for current_source in source_candidates:
            if current_source in checked:
                continue
            checked.add(current_source)
            movies = self._load_raw_library(current_source, force_refresh=False)
            for movie in movies:
                if movie.get("path") == movie_path:
                    movie.update(updates)
                    self._save_raw_library(current_source, movies)
                    return self._decorate_movie(movie, favorite_paths, source=current_source)
        raise ValueError("未找到对应的视频条目")

    def save_custom_info(
        self,
        movie_path: str,
        updates: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        current = self.cache.get_custom_info(movie_path)
        current.update(updates)
        self.cache.save_custom_info(movie_path, current)
        try:
            return self.update_library_fields(movie_path, updates, source=source)
        except ValueError:
            movie = self.get_movie(movie_path, source=source)
            if not movie:
                raise
            movie.update(updates)
            favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
            return self._decorate_movie(movie, favorite_paths, source=movie.get("source"))

    def toggle_favorite(self, movie_path: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        if self.cache.is_favorite(movie_path):
            self.cache.remove_favorite(movie_path)
        else:
            self.cache.add_favorite(movie)
        return self.get_movie(movie_path) or movie

    def add_recent(self, movie_path: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        self.cache.add_recent_play(movie)
        return movie

    def get_stats(self) -> dict[str, int]:
        try:
            remote_count = len(self.remote_library._cached_list) if self.remote_library._cached_list is not None else 0
            local_count = len(self.local_library._cached_list) if self.local_library._cached_list is not None else 0
            return {
                "all": remote_count + local_count,
                "remote": remote_count,
                "local": local_count,
                "favorite": len(self.cache.get_favorites()),
                "recent": len(self.cache.get_recent_play()),
            }
        except Exception:
            return {
                "all": len(self.get_library("remote", force_refresh=False)) + len(self.get_library("local", force_refresh=False)),
                "remote": len(self.get_library("remote", force_refresh=False)),
                "local": len(self.get_library("local", force_refresh=False)),
                "favorite": len(self.cache.get_favorites()),
                "recent": len(self.cache.get_recent_play()),
            }

    def clear_library_cache(self, source: str | None = None) -> None:
        if source == "local":
            self.local_library.clear_cache()
            return
        if source == "remote":
            self.remote_library.clear_cache()
            return
        self.remote_library.clear_cache()
        self.local_library.clear_cache()

    def clear_all_cache(self) -> None:
        self.clear_library_cache()
        release_logger_handlers()
        try:
            if self.config.COVERS_DIR.exists():
                shutil.rmtree(self.config.COVERS_DIR, ignore_errors=True)
            self.config.COVERS_DIR.mkdir(exist_ok=True)
            cache_targets = [
                self.config.DATA_DIR / "app.log",
                self.config.DATA_DIR / "video_library_cache.json",
                self.config.DATA_DIR / "local_video_library_cache.json",
                self.config.DATA_DIR / "playback_progress.json",
            ]
            for file_path in cache_targets:
                if file_path.exists():
                    file_path.unlink(missing_ok=True)
            potplayer_cache = self.config.DATA_DIR / "potplayer_cache"
            if potplayer_cache.exists():
                shutil.rmtree(potplayer_cache, ignore_errors=True)
        finally:
            reconfigure_logger()

    def clear_all_data(self) -> None:
        release_logger_handlers()
        try:
            try:
                from core.openlist_manager import openlist_manager
                openlist_manager.stop()
                openlist_manager._stop_event.set()
            except Exception:
                pass

            self.clear_library_cache()
            shutil.rmtree(self.config.COVERS_DIR, ignore_errors=True)
            if FIRST_RUN_FLAG.exists():
                FIRST_RUN_FLAG.unlink(missing_ok=True)

            if self.config.DATA_DIR.exists():
                for item in self.config.DATA_DIR.iterdir():
                    try:
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink(missing_ok=True)
                    except Exception:
                        logger.warning("无法删除: %s（可能被其他进程占用）", item)

            if self.config.DATA_DIR.exists():
                remaining = list(self.config.DATA_DIR.iterdir())
                if remaining:
                    data_dir_str = str(self.config.DATA_DIR)
                    if os.name == "nt":
                        subprocess.run(
                            ["cmd", "/c", "rd", "/s", "/q", data_dir_str],
                            capture_output=True, timeout=30,
                        )
                    else:
                        subprocess.run(
                            ["rm", "-rf", data_dir_str],
                            capture_output=True, timeout=30,
                        )

            self.config.DATA_DIR.mkdir(exist_ok=True)
            self.config.COVERS_DIR.mkdir(exist_ok=True)
            self.config.WEBDAV_HOST = ""
            self.config.WEBDAV_USER = ""
            self.config.WEBDAV_PASS = ""
            self.config.REMOTE_PROVIDER = "webdav"
            self.config.REMOTE_PROFILES = {}
            self.config.SAVED_MOUNT_DIRS = []
            self.config.SCAN_MAX_DEPTH = 2
            self.config.LOCAL_MOUNT_DIRS = []
            self.config.LOCAL_SCAN_MAX_DEPTH = 3
            self.config.POTPLAYER_PATH = ""
            self.config.VLC_PATH = ""
            self.config.DEFAULT_PLAYER = "potplayer"
            self.config.TMDB_API_KEY = ""
            self.config.TMDB_API_BASE = "https://api.themoviedb.org/3"
            self.config.TMDB_WEB_BASE = "https://www.themoviedb.org"
            self.config.TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
            self.config.ENABLE_AUTO_SCRAPE = True
            self.config.SCRAPE_SOURCE = "auto"
            self.config.VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"]
            self.config.UI_THEME = "amber"
            self.config.INTERFACE_THEME = "amber"
            self.config.INTERFACE_LANGUAGE = "zh"
            self.config.OPENLIST_ENABLED = False
            self.config.OPENLIST_PORT = 5244
            self.config.OPENLIST_ADMIN_PASSWORD = ""
            self.config.OPENLIST_AUTO_START = True
            self.config.OPENLIST_BINARY_VERSION = ""
            self.config.save_config()

            try:
                from core.openlist_manager import openlist_manager
                openlist_manager.reload_config()
            except Exception:
                pass
        finally:
            reconfigure_logger(include_file_handler=False)

    def save_playback_progress(self, movie_path: str, progress: float, duration: float) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        self.cache.save_playback_progress(movie_path, progress, duration)
        return {"success": True, "movie": movie}

    def get_playback_progress(self, movie_path: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        progress = self.cache.get_playback_progress(movie_path)
        return {"success": True, "progress": progress, "movie": movie}

    def clear_playback_progress(self, movie_path: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        self.cache.clear_playback_progress(movie_path)
        return {"success": True, "movie": movie}

    def get_all_tags(self) -> dict[str, int]:
        tags = self.cache.get_all_tags()
        result = {}
        for tag, movies in tags.items():
            if isinstance(movies, list):
                result[tag] = len(movies)
        return result

    def get_movie_tags(self, movie_path: str) -> list[str]:
        return self.cache.get_movie_tags(movie_path)

    def add_movie_tag(self, movie_path: str, tag: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        self.cache.add_movie_tag(movie_path, tag)
        return self.get_movie(movie_path) or movie

    def remove_movie_tag(self, movie_path: str, tag: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        self.cache.remove_movie_tag(movie_path, tag)
        return self.get_movie(movie_path) or movie

    def get_movies_by_tag(self, tag: str, source: str = "remote") -> list[dict[str, Any]]:
        movie_paths = self.cache.get_movies_by_tag(tag)
        movies = []
        for path in movie_paths:
            movie = self.get_movie(path, source=self._source_for_path(path))
            if movie:
                movies.append(movie)
        return movies
