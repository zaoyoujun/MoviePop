from __future__ import annotations

import copy
import os
import string
from pathlib import Path
from typing import Any

from config.app_config import AppConfig
from core.remote_source import make_remote_client
from core.video_library import VideoLibraryManager
from core.local_video_library import LocalVideoLibraryManager
from utils.logger import get_logger

logger = get_logger()


def build_remote_client(config: AppConfig, provider: str | None = None):
    return make_remote_client(config, provider or config.REMOTE_PROVIDER)


class ConfigService:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.config.load_config()

    def _snapshot(self) -> dict[str, Any]:
        return {
            "remote_provider": self.config.REMOTE_PROVIDER,
            "remote_profiles": copy.deepcopy(self.config.get_remote_profiles()),
            "webdav_host": self.config.WEBDAV_HOST,
            "webdav_user": self.config.WEBDAV_USER,
            "webdav_pass": self.config.WEBDAV_PASS,
            "remote_cookie": self.config.REMOTE_COOKIE,
            "scan_max_depth": self.config.SCAN_MAX_DEPTH,
            "saved_mount_dirs": list(self.config.SAVED_MOUNT_DIRS),
            "local_scan_max_depth": self.config.LOCAL_SCAN_MAX_DEPTH,
            "local_mount_dirs": list(self.config.LOCAL_MOUNT_DIRS),
            "potplayer_path": self.config.POTPLAYER_PATH,
            "vlc_path": self.config.VLC_PATH,
            "default_player": self.config.DEFAULT_PLAYER,
            "video_formats": self.config.VIDEO_FORMATS,
            "enable_auto_scrape": self.config.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.config.SCRAPE_SOURCE,
            "tmdb_api_key": self.config.TMDB_API_KEY,
            "tmdb_api_base": self.config.TMDB_API_BASE,
            "tmdb_web_base": self.config.TMDB_WEB_BASE,
            "tmdb_image_base": self.config.TMDB_IMAGE_BASE,
            "interface_theme": self.config.INTERFACE_THEME,
            "ui_theme": self.config.UI_THEME,
            "interface_language": self.config.INTERFACE_LANGUAGE,
        }

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        remote_profiles = payload.get("remote_profiles")
        if isinstance(remote_profiles, dict):
            normalized_profiles = self.config.get_remote_profiles()
            for provider, values in remote_profiles.items():
                key = self.config.normalize_remote_provider(provider)
                if not isinstance(values, dict):
                    continue
                normalized_profiles[key] = {
                    "webdav_host": str(values.get("webdav_host", normalized_profiles.get(key, {}).get("webdav_host", ""))).strip(),
                    "webdav_user": str(values.get("webdav_user", normalized_profiles.get(key, {}).get("webdav_user", ""))).strip(),
                    "webdav_pass": str(values.get("webdav_pass", normalized_profiles.get(key, {}).get("webdav_pass", ""))).strip(),
                    "remote_cookie": str(values.get("remote_cookie", normalized_profiles.get(key, {}).get("remote_cookie", ""))).strip(),
                    "saved_mount_dirs": [
                        str(item).strip()
                        for item in self.config.normalize_remote_mount_dirs(
                            key,
                            values.get(
                                "saved_mount_dirs",
                                normalized_profiles.get(key, {}).get("saved_mount_dirs", []),
                            )
                            if isinstance(
                                values.get(
                                    "saved_mount_dirs",
                                    normalized_profiles.get(key, {}).get("saved_mount_dirs", []),
                                ),
                                list,
                            )
                            else [],
                        )
                    ],
                }
            self.config.REMOTE_PROFILES = normalized_profiles

        self.config.REMOTE_PROVIDER = self.config.normalize_remote_provider(
            payload.get("remote_provider", self.config.REMOTE_PROVIDER)
        )
        active_profile = self.config.get_remote_profiles().get(self.config.REMOTE_PROVIDER, {})
        self.config.WEBDAV_HOST = str(payload.get("webdav_host", active_profile.get("webdav_host", self.config.WEBDAV_HOST))).strip()
        self.config.WEBDAV_USER = str(payload.get("webdav_user", active_profile.get("webdav_user", self.config.WEBDAV_USER))).strip()
        self.config.WEBDAV_PASS = str(payload.get("webdav_pass", active_profile.get("webdav_pass", self.config.WEBDAV_PASS))).strip()
        self.config.REMOTE_COOKIE = str(payload.get("remote_cookie", active_profile.get("remote_cookie", self.config.REMOTE_COOKIE))).strip()
        self.config.SCAN_MAX_DEPTH = int(payload.get("scan_max_depth", self.config.SCAN_MAX_DEPTH or 2))

        saved_mount_dirs = payload.get("saved_mount_dirs")
        if isinstance(saved_mount_dirs, list):
            self.config.SAVED_MOUNT_DIRS = self.config.normalize_remote_mount_dirs(
                self.config.REMOTE_PROVIDER,
                saved_mount_dirs,
            )
        else:
            self.config.SAVED_MOUNT_DIRS = self.config.normalize_remote_mount_dirs(
                self.config.REMOTE_PROVIDER,
                active_profile.get("saved_mount_dirs", self.config.SAVED_MOUNT_DIRS),
            )
        self.config._sync_active_remote_profile()

        self.config.LOCAL_SCAN_MAX_DEPTH = int(
            payload.get("local_scan_max_depth", self.config.LOCAL_SCAN_MAX_DEPTH or 3)
        )
        local_mount_dirs = payload.get("local_mount_dirs")
        if isinstance(local_mount_dirs, list):
            self.config.LOCAL_MOUNT_DIRS = [str(item).strip() for item in local_mount_dirs if str(item).strip()]

        self.config.POTPLAYER_PATH = str(payload.get("potplayer_path", self.config.POTPLAYER_PATH)).strip()
        self.config.VLC_PATH = str(payload.get("vlc_path", self.config.VLC_PATH)).strip()
        default_player = str(payload.get("default_player", self.config.DEFAULT_PLAYER)).strip().lower()
        self.config.DEFAULT_PLAYER = default_player if default_player in {"potplayer", "vlc"} else "potplayer"

        video_formats = payload.get("video_formats")
        if isinstance(video_formats, list):
            self.config.VIDEO_FORMATS = [str(fmt).strip() for fmt in video_formats if str(fmt).strip()]

        self.config.ENABLE_AUTO_SCRAPE = bool(payload.get("enable_auto_scrape", self.config.ENABLE_AUTO_SCRAPE))

        self.config.SCRAPE_SOURCE = "auto"
        self.config.TMDB_API_KEY = str(payload.get("tmdb_api_key", self.config.TMDB_API_KEY)).strip()
        self.config.TMDB_API_BASE = str(payload.get("tmdb_api_base", self.config.TMDB_API_BASE)).strip() or "https://api.themoviedb.org/3"
        self.config.TMDB_WEB_BASE = str(payload.get("tmdb_web_base", self.config.TMDB_WEB_BASE)).strip() or "https://www.themoviedb.org"
        self.config.TMDB_IMAGE_BASE = str(payload.get("tmdb_image_base", self.config.TMDB_IMAGE_BASE)).strip() or "https://image.tmdb.org/t/p/w500"

        interface_theme = payload.get("ui_theme", payload.get("interface_theme", self.config.UI_THEME))
        self.config.UI_THEME = self.config.normalize_theme(interface_theme)
        self.config.INTERFACE_THEME = self.config.UI_THEME

        interface_language = str(payload.get("interface_language", self.config.INTERFACE_LANGUAGE)).strip().lower()
        self.config.INTERFACE_LANGUAGE = interface_language if interface_language in {"zh", "en"} else "zh"

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._apply_payload(snapshot)

    def get_public_config(self) -> dict[str, Any]:
        return {
            "remote_provider": self.config.REMOTE_PROVIDER,
            "remote_provider_label": self.config.get_remote_provider_label(),
            "remote_profiles": copy.deepcopy(self.config.get_remote_profiles()),
            "webdav_host": self.config.WEBDAV_HOST,
            "webdav_user": self.config.WEBDAV_USER,
            "webdav_pass": self.config.WEBDAV_PASS,
            "remote_cookie": self.config.REMOTE_COOKIE,
            "scan_max_depth": self.config.SCAN_MAX_DEPTH,
            "saved_mount_dirs": list(self.config.SAVED_MOUNT_DIRS),
            "local_scan_max_depth": self.config.LOCAL_SCAN_MAX_DEPTH,
            "local_mount_dirs": list(self.config.LOCAL_MOUNT_DIRS),
            "potplayer_path": self.config.POTPLAYER_PATH,
            "vlc_path": self.config.VLC_PATH,
            "default_player": self.config.DEFAULT_PLAYER,
            "video_formats": self.config.VIDEO_FORMATS,
            "enable_auto_scrape": self.config.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.config.SCRAPE_SOURCE,
            "tmdb_api_key": self.config.TMDB_API_KEY,
            "tmdb_api_base": self.config.TMDB_API_BASE,
            "tmdb_web_base": self.config.TMDB_WEB_BASE,
            "tmdb_image_base": self.config.TMDB_IMAGE_BASE,
            "interface_theme": self.config.INTERFACE_THEME,
            "ui_theme": self.config.UI_THEME,
            "available_themes": list(self.config.AVAILABLE_THEMES),
            "interface_language": self.config.INTERFACE_LANGUAGE,
            "has_basic_config": self.config.has_basic_config(),
            "has_local_config": self.config.has_local_config(),
            "has_any_library": self.config.has_basic_config() or self.config.has_local_config(),
            "openlist_enabled": self.config.OPENLIST_ENABLED,
            "openlist_port": self.config.OPENLIST_PORT or 5244,
            "openlist_admin_password": self.config.OPENLIST_ADMIN_PASSWORD,
            "openlist_auto_start": self.config.OPENLIST_AUTO_START,
            "openlist_binary_version": self.config.OPENLIST_BINARY_VERSION,
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        previous_remote_signature = (
            self.config.REMOTE_PROVIDER,
            copy.deepcopy(self.config.get_remote_profiles()),
            self.config.WEBDAV_HOST,
            self.config.WEBDAV_USER,
            self.config.WEBDAV_PASS,
            self.config.REMOTE_COOKIE,
            tuple(self.config.SAVED_MOUNT_DIRS),
            self.config.SCAN_MAX_DEPTH,
        )
        previous_local_signature = (
            tuple(self.config.LOCAL_MOUNT_DIRS),
            self.config.LOCAL_SCAN_MAX_DEPTH,
        )

        self._apply_payload(payload)
        self.config.save_config()

        current_remote_signature = (
            self.config.REMOTE_PROVIDER,
            copy.deepcopy(self.config.get_remote_profiles()),
            self.config.WEBDAV_HOST,
            self.config.WEBDAV_USER,
            self.config.WEBDAV_PASS,
            self.config.REMOTE_COOKIE,
            tuple(self.config.SAVED_MOUNT_DIRS),
            self.config.SCAN_MAX_DEPTH,
        )
        current_local_signature = (
            tuple(self.config.LOCAL_MOUNT_DIRS),
            self.config.LOCAL_SCAN_MAX_DEPTH,
        )

        if previous_remote_signature != current_remote_signature:
            VideoLibraryManager().clear_cache()
        if previous_local_signature != current_local_signature:
            LocalVideoLibraryManager().clear_cache()

        return self.get_public_config()

    def test_connection(self, payload: dict[str, Any] | None = None) -> tuple[bool, str]:
        if payload:
            snapshot = self._snapshot()
            try:
                self._apply_payload(payload)
                return build_remote_client(self.config).test_connection()
            finally:
                self._restore_snapshot(snapshot)
        return build_remote_client(self.config).test_connection()

    def list_directories(self, path: str = "/", payload: dict[str, Any] | None = None) -> list[dict[str, str]]:
        if payload:
            snapshot = self._snapshot()
            try:
                self._apply_payload(payload)
                return build_remote_client(self.config).list_directories(path)
            finally:
                self._restore_snapshot(snapshot)
        return build_remote_client(self.config).list_directories(path)

    def list_local_directories(self, path: str = "") -> list[dict[str, str]]:
        if not path:
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({"name": drive.rstrip("\\"), "full_path": drive})
            return drives

        root = Path(path)
        if not root.exists() or not root.is_dir():
            raise ValueError("本地目录不存在")

        directories = []
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                directories.append({"name": child.name, "full_path": str(child.resolve())})
        return directories
