"""
应用配置模块
使用 JSON 文件持久化配置，替代 INI 文件
"""
import json
import os
from pathlib import Path


class AppConfig:
    """应用配置单例，管理所有运行时配置"""
    _instance = None

    # 可用的 UI 主题列表
    AVAILABLE_THEMES = ("amber", "graphite", "forest", "coast")
    PLAYER_HWDEC_CHOICES = ("auto-copy", "auto-safe", "no")
    PLAYER_ENHANCEMENT_CHOICES = (
        "original",
        "clean",
        "sharp",
        "clarity",
        "anime_light",
        "anime_strong",
        "ai_general",
        "ai_quality",
    )
    PLAYER_FRAME_PROFILE_CHOICES = ("off", "natural", "smooth", "display")
    PLAYER_SUBTITLE_MODE_CHOICES = ("auto", "off")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_defaults()
        return cls._instance

    def _init_defaults(self):
        """初始化所有默认配置值"""
        # 目录路径
        self.BASE_DIR = Path(os.environ.get("MOVIEPOP_BACKEND_BASE_DIR") or Path(__file__).resolve().parent)
        self.DATA_DIR = self.BASE_DIR / "data"
        self.COVERS_DIR = self.BASE_DIR / "covers"
        self.CONFIG_FILE = self.DATA_DIR / "config.json"

        # 服务器配置
        self.SERVER_PORT = int(os.environ.get("MOVIEPOP_BACKEND_PORT") or 8000)

        # OpenList 内置服务器配置
        self.OPENLIST_ENABLED = False
        self.OPENLIST_PORT = 5244
        self.OPENLIST_AUTO_START = False
        self.OPENLIST_AUTO_LOGIN = True
        self.OPENLIST_AUTO_RESET_PASSWORD = True
        self.OPENLIST_ADMIN_PASSWORD = ""
        self.OPENLIST_BINARY_VERSION = ""

        # 远程数据源配置
        self.REMOTE_PROVIDER = "webdav"  # webdav / openlist
        self.WEBDAV_HOST = ""
        self.WEBDAV_USER = ""
        self.WEBDAV_PASS = ""
        self.REMOTE_COOKIE = ""
        self.SCAN_MAX_DEPTH = 4
        self.SAVED_MOUNT_DIRS = []

        # 本地数据源配置
        self.LOCAL_MOUNT_DIRS = []
        self.LOCAL_SCAN_MAX_DEPTH = 4

        # 视频格式支持
        self.VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"]

        # 封面刮削配置（首期暂不实现完整刮削，仅保留配置）
        self.ENABLE_AUTO_SCRAPE = True
        self.SCRAPE_SOURCE = "auto"
        self.TMDB_API_KEY = ""
        self.TMDB_API_BASE = "https://api.themoviedb.org/3"
        self.TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
        self.DOUBAN_COOKIE = ""

        # UI 配置
        self.UI_THEME = "amber"
        self.INTERFACE_THEME = "amber"
        self.INTERFACE_LANGUAGE = "zh"

        # 播放器配置。仅保存经过白名单校验的预设 ID，绝不透传 MPV 参数。
        self.PLAYER_HWDEC = "auto-copy"
        self.PLAYER_ENHANCEMENT_PROFILE = "original"
        self.PLAYER_FRAME_PROFILE = "off"
        self.PLAYER_SUBTITLE_MODE = "auto"
        self.PLAYER_SHOW_PLAYBACK_INFO = True
        self.PLAYER_ALWAYS_ON_TOP = False
        self.PLAYER_DEFAULT_VOLUME = 80

        # 确保数据目录存在
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.COVERS_DIR.mkdir(parents=True, exist_ok=True)

    def load_config(self):
        """从 JSON 文件加载配置，如果文件不存在则使用默认值"""
        if not self.CONFIG_FILE.exists():
            self.save_config()
            return

        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 服务器配置
            self.SERVER_PORT = data.get("server_port", self.SERVER_PORT)

            # OpenList 内置服务器配置
            self.OPENLIST_ENABLED = data.get("openlist_enabled", self.OPENLIST_ENABLED)
            self.OPENLIST_PORT = data.get("openlist_port", self.OPENLIST_PORT)
            self.OPENLIST_AUTO_START = data.get("openlist_auto_start", self.OPENLIST_AUTO_START)
            self.OPENLIST_AUTO_LOGIN = data.get("openlist_auto_login", self.OPENLIST_AUTO_LOGIN)
            self.OPENLIST_AUTO_RESET_PASSWORD = data.get("openlist_auto_reset_password", self.OPENLIST_AUTO_RESET_PASSWORD)
            self.OPENLIST_ADMIN_PASSWORD = data.get("openlist_admin_password", self.OPENLIST_ADMIN_PASSWORD)
            self.OPENLIST_BINARY_VERSION = data.get("openlist_binary_version", self.OPENLIST_BINARY_VERSION)

            # 远程数据源
            self.REMOTE_PROVIDER = data.get("remote_provider", self.REMOTE_PROVIDER)
            self.WEBDAV_HOST = data.get("webdav_host", self.WEBDAV_HOST)
            self.WEBDAV_USER = data.get("webdav_user", self.WEBDAV_USER)
            self.WEBDAV_PASS = data.get("webdav_pass", self.WEBDAV_PASS)
            self.REMOTE_COOKIE = data.get("remote_cookie", self.REMOTE_COOKIE)
            self.SCAN_MAX_DEPTH = max(4, int(data.get("scan_max_depth", self.SCAN_MAX_DEPTH) or 4))
            self.SAVED_MOUNT_DIRS = data.get("saved_mount_dirs", self.SAVED_MOUNT_DIRS)

            # 本地数据源
            self.LOCAL_MOUNT_DIRS = data.get("local_mount_dirs", self.LOCAL_MOUNT_DIRS)
            self.LOCAL_SCAN_MAX_DEPTH = max(4, int(data.get("local_scan_max_depth", self.LOCAL_SCAN_MAX_DEPTH) or 4))

            # 视频格式
            self.VIDEO_FORMATS = data.get("video_formats", self.VIDEO_FORMATS)

            # 封面刮削
            self.ENABLE_AUTO_SCRAPE = data.get("enable_auto_scrape", self.ENABLE_AUTO_SCRAPE)
            self.SCRAPE_SOURCE = data.get("scrape_source", self.SCRAPE_SOURCE)
            self.TMDB_API_KEY = data.get("tmdb_api_key", self.TMDB_API_KEY)
            self.TMDB_API_BASE = data.get("tmdb_api_base", self.TMDB_API_BASE)
            self.TMDB_IMAGE_BASE = data.get("tmdb_image_base", self.TMDB_IMAGE_BASE)
            self.DOUBAN_COOKIE = data.get("douban_cookie", self.DOUBAN_COOKIE)

            # UI 配置
            self.UI_THEME = data.get("ui_theme", self.UI_THEME)
            self.INTERFACE_THEME = data.get("interface_theme", self.INTERFACE_THEME)
            self.INTERFACE_LANGUAGE = data.get("interface_language", self.INTERFACE_LANGUAGE)

            # 播放器设置：旧配置不存在时保留默认值，非法值自动回退到安全默认值。
            self.PLAYER_HWDEC = self._choice(
                data.get("player_hwdec", self.PLAYER_HWDEC),
                self.PLAYER_HWDEC,
                self.PLAYER_HWDEC_CHOICES,
            )
            self.PLAYER_ENHANCEMENT_PROFILE = self._choice(
                data.get("player_enhancement_profile", self.PLAYER_ENHANCEMENT_PROFILE),
                self.PLAYER_ENHANCEMENT_PROFILE,
                self.PLAYER_ENHANCEMENT_CHOICES,
            )
            self.PLAYER_FRAME_PROFILE = self._choice(
                data.get("player_frame_profile", self.PLAYER_FRAME_PROFILE),
                self.PLAYER_FRAME_PROFILE,
                self.PLAYER_FRAME_PROFILE_CHOICES,
            )
            self.PLAYER_SUBTITLE_MODE = self._choice(
                data.get("player_subtitle_mode", self.PLAYER_SUBTITLE_MODE),
                self.PLAYER_SUBTITLE_MODE,
                self.PLAYER_SUBTITLE_MODE_CHOICES,
            )
            self.PLAYER_SHOW_PLAYBACK_INFO = self._coerce_bool(
                data.get("player_show_playback_info", self.PLAYER_SHOW_PLAYBACK_INFO),
                self.PLAYER_SHOW_PLAYBACK_INFO,
            )
            self.PLAYER_ALWAYS_ON_TOP = self._coerce_bool(
                data.get("player_always_on_top", self.PLAYER_ALWAYS_ON_TOP),
                self.PLAYER_ALWAYS_ON_TOP,
            )
            self.PLAYER_DEFAULT_VOLUME = self._bounded_int(
                data.get("player_default_volume", self.PLAYER_DEFAULT_VOLUME),
                self.PLAYER_DEFAULT_VOLUME,
                0,
                100,
            )

        except (json.JSONDecodeError, IOError):
            # 配置文件损坏，使用默认值
            self.save_config()

        if os.environ.get("MOVIEPOP_BACKEND_PORT"):
            self.SERVER_PORT = int(os.environ["MOVIEPOP_BACKEND_PORT"])

    def save_config(self):
        """将当前配置保存到 JSON 文件"""
        data = {
            "server_port": self.SERVER_PORT,
            "openlist_enabled": self.OPENLIST_ENABLED,
            "openlist_port": self.OPENLIST_PORT,
            "openlist_auto_start": self.OPENLIST_AUTO_START,
            "openlist_auto_login": self.OPENLIST_AUTO_LOGIN,
            "openlist_auto_reset_password": self.OPENLIST_AUTO_RESET_PASSWORD,
            "openlist_admin_password": self.OPENLIST_ADMIN_PASSWORD,
            "openlist_binary_version": self.OPENLIST_BINARY_VERSION,
            "remote_provider": self.REMOTE_PROVIDER,
            "webdav_host": self.WEBDAV_HOST,
            "webdav_user": self.WEBDAV_USER,
            "webdav_pass": self.WEBDAV_PASS,
            "remote_cookie": self.REMOTE_COOKIE,
            "scan_max_depth": self.SCAN_MAX_DEPTH,
            "saved_mount_dirs": self.SAVED_MOUNT_DIRS,
            "local_mount_dirs": self.LOCAL_MOUNT_DIRS,
            "local_scan_max_depth": self.LOCAL_SCAN_MAX_DEPTH,
            "video_formats": self.VIDEO_FORMATS,
            "enable_auto_scrape": self.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.SCRAPE_SOURCE,
            "tmdb_api_key": self.TMDB_API_KEY,
            "tmdb_api_base": self.TMDB_API_BASE,
            "tmdb_image_base": self.TMDB_IMAGE_BASE,
            "douban_cookie": self.DOUBAN_COOKIE,
            "ui_theme": self.UI_THEME,
            "interface_theme": self.INTERFACE_THEME,
            "interface_language": self.INTERFACE_LANGUAGE,
            "player_hwdec": self.PLAYER_HWDEC,
            "player_enhancement_profile": self.PLAYER_ENHANCEMENT_PROFILE,
            "player_frame_profile": self.PLAYER_FRAME_PROFILE,
            "player_subtitle_mode": self.PLAYER_SUBTITLE_MODE,
            "player_show_playback_info": self.PLAYER_SHOW_PLAYBACK_INFO,
            "player_always_on_top": self.PLAYER_ALWAYS_ON_TOP,
            "player_default_volume": self.PLAYER_DEFAULT_VOLUME,
        }

        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_public_config(self) -> dict:
        """返回可公开给前端的配置（不含密码等敏感信息）"""
        return {
            "openlist_enabled": self.OPENLIST_ENABLED,
            "openlist_port": self.OPENLIST_PORT,
            "openlist_auto_start": self.OPENLIST_AUTO_START,
            "openlist_auto_login": self.OPENLIST_AUTO_LOGIN,
            "openlist_auto_reset_password": self.OPENLIST_AUTO_RESET_PASSWORD,
            "openlist_admin_username": "admin",
            "openlist_admin_password": self.OPENLIST_ADMIN_PASSWORD,
            "openlist_username": "admin",
            "openlist_password": self.OPENLIST_ADMIN_PASSWORD,
            "remote_provider": self.REMOTE_PROVIDER,
            "webdav_host": self.WEBDAV_HOST,
            "webdav_user": self.WEBDAV_USER,
            "scan_max_depth": self.SCAN_MAX_DEPTH,
            "saved_mount_dirs": list(self.SAVED_MOUNT_DIRS),
            "local_mount_dirs": list(self.LOCAL_MOUNT_DIRS),
            "local_scan_max_depth": self.LOCAL_SCAN_MAX_DEPTH,
            "video_formats": list(self.VIDEO_FORMATS),
            "enable_auto_scrape": self.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.SCRAPE_SOURCE,
            "scrapeSource": self.SCRAPE_SOURCE,
            "tmdb_api_key": self.TMDB_API_KEY,
            "tmdbApiKey": self.TMDB_API_KEY,
            "tmdb_api_base": self.TMDB_API_BASE,
            "tmdb_image_base": self.TMDB_IMAGE_BASE,
            "douban_cookie": self.DOUBAN_COOKIE,
            "doubanCookie": self.DOUBAN_COOKIE,
            "interface_theme": self.INTERFACE_THEME,
            "ui_theme": self.UI_THEME,
            "available_themes": list(self.AVAILABLE_THEMES),
            "interface_language": self.INTERFACE_LANGUAGE,
        }

    @staticmethod
    def _choice(value, default: str, choices: tuple[str, ...]) -> str:
        candidate = str(value or "").strip()
        return candidate if candidate in choices else default

    @staticmethod
    def _coerce_bool(value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _bounded_int(value, default: int, low: int, high: int) -> int:
        try:
            return max(low, min(high, int(value)))
        except (TypeError, ValueError):
            return default

    def get_player_settings(self) -> dict:
        """Return the safe, version-stable preferences used by new player windows."""
        return {
            "hwdec": self.PLAYER_HWDEC,
            "enhancement_profile": self.PLAYER_ENHANCEMENT_PROFILE,
            "frame_profile": self.PLAYER_FRAME_PROFILE,
            "subtitle_mode": self.PLAYER_SUBTITLE_MODE,
            "show_playback_info": bool(self.PLAYER_SHOW_PLAYBACK_INFO),
            "always_on_top": bool(self.PLAYER_ALWAYS_ON_TOP),
            "volume": int(self.PLAYER_DEFAULT_VOLUME),
        }

    def update_player_settings(self, values: dict) -> dict:
        """Update player preferences from a narrow UI-facing allowlist."""
        if not isinstance(values, dict):
            values = {}

        if "hwdec" in values:
            self.PLAYER_HWDEC = self._choice(values.get("hwdec"), self.PLAYER_HWDEC, self.PLAYER_HWDEC_CHOICES)
        if "enhancement_profile" in values or "enhancementProfile" in values:
            self.PLAYER_ENHANCEMENT_PROFILE = self._choice(
                values.get("enhancement_profile", values.get("enhancementProfile")),
                self.PLAYER_ENHANCEMENT_PROFILE,
                self.PLAYER_ENHANCEMENT_CHOICES,
            )
        if "frame_profile" in values or "frameProfile" in values:
            self.PLAYER_FRAME_PROFILE = self._choice(
                values.get("frame_profile", values.get("frameProfile")),
                self.PLAYER_FRAME_PROFILE,
                self.PLAYER_FRAME_PROFILE_CHOICES,
            )
        if "subtitle_mode" in values or "subtitleMode" in values:
            self.PLAYER_SUBTITLE_MODE = self._choice(
                values.get("subtitle_mode", values.get("subtitleMode")),
                self.PLAYER_SUBTITLE_MODE,
                self.PLAYER_SUBTITLE_MODE_CHOICES,
            )
        if "show_playback_info" in values or "showPlaybackInfo" in values:
            self.PLAYER_SHOW_PLAYBACK_INFO = self._coerce_bool(
                values.get("show_playback_info", values.get("showPlaybackInfo")),
                self.PLAYER_SHOW_PLAYBACK_INFO,
            )
        if "always_on_top" in values or "alwaysOnTop" in values:
            self.PLAYER_ALWAYS_ON_TOP = self._coerce_bool(
                values.get("always_on_top", values.get("alwaysOnTop")),
                self.PLAYER_ALWAYS_ON_TOP,
            )
        if "volume" in values:
            self.PLAYER_DEFAULT_VOLUME = self._bounded_int(values.get("volume"), self.PLAYER_DEFAULT_VOLUME, 0, 100)

        return self.get_player_settings()

    def normalize_remote_provider(self, provider: str) -> str:
        """标准化远程数据源提供者标识"""
        value = str(provider or "").strip().lower()
        if value in {"webdav", "openlist"}:
            return value
        return "webdav"
