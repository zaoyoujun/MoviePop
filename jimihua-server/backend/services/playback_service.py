from __future__ import annotations

import os
import subprocess
from typing import Any
from urllib.parse import quote, urlencode, unquote

from config.app_config import AppConfig
from core.remote_source import make_remote_client
from utils.logger import get_logger

logger = get_logger()


def build_remote_client(config: AppConfig, provider: str | None = None):
    return make_remote_client(config, provider or config.REMOTE_PROVIDER)


class PlaybackService:
    def __init__(self, library_service) -> None:
        self.config = AppConfig()
        self.config.load_config()
        self.library_service = library_service

    def _resolve_player(self) -> tuple[str, str]:
        if (
            self.config.DEFAULT_PLAYER == "vlc"
            and self.config.VLC_PATH
            and os.path.exists(self.config.VLC_PATH)
        ):
            return self.config.VLC_PATH, "VLC"
        if self.config.POTPLAYER_PATH and os.path.exists(self.config.POTPLAYER_PATH):
            return self.config.POTPLAYER_PATH, "PotPlayer"
        if self.config.VLC_PATH and os.path.exists(self.config.VLC_PATH):
            return self.config.VLC_PATH, "VLC"
        raise FileNotFoundError("未找到可用播放器，请先在设置中配置 PotPlayer 或 VLC。")

    def build_proxy_play_url(self, movie_path: str, episode_index: int = 0) -> str:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        file_path = movie.get("path", "")
        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = movie.get("episode_files", [])
            if 0 <= episode_index < len(episode_files):
                file_path = episode_files[episode_index]

        if not file_path:
            raise ValueError("视频路径无效")

        query = urlencode(
            {
                "movie_path": file_path,
                "provider": movie.get("remote_provider") or "",
            }
        )
        raw_name = os.path.basename(str(file_path).rstrip("/")) or "media"
        display_name = unquote(raw_name) or "media"
        encoded_name = quote(display_name, safe="._-()[] ")
        encoded_name = encoded_name.replace(" ", "%20")
        from backend.server import resolved_port
        return f"http://127.0.0.1:{resolved_port}/api/stream/media/{encoded_name}?{query}"

    def play(self, movie_path: str, episode_index: int = 0) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        file_path = movie.get("path", "")
        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = movie.get("episode_files", [])
            if 0 <= episode_index < len(episode_files):
                file_path = episode_files[episode_index]

        if not file_path:
            raise ValueError("视频路径无效")

        player_path, player_name = self._resolve_player()
        is_local_source = movie.get("source") == "local"
        if is_local_source:
            play_target = file_path
        else:
            play_target = build_remote_client(self.config, movie.get("remote_provider")).get_file_url(file_path)
        cmd = [player_path]

        if player_name == "PotPlayer":
            cache_dir = self.config.DATA_DIR / "potplayer_cache"
            cache_dir.mkdir(exist_ok=True)
            cmd.extend(
                [
                    "/buftime:5",
                    "/http_bufsize:102400",
                    "/diskcache:1",
                    "/diskcachesize:2048",
                    f'/cachepath:"{cache_dir.absolute()}"',
                ]
            )
        elif not is_local_source:
            cmd.append("--network-caching=3000")

        cmd.append(play_target)
        subprocess.Popen(cmd, shell=False)
        self.library_service.add_recent(movie_path)
        logger.info("启动播放器成功: %s -> %s", player_name, play_target)
        return {
            "player": player_name,
            "file_path": file_path,
            "play_url": play_target,
            "source": movie.get("source"),
        }
