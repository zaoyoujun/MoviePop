from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib import request as urlrequest
from urllib.error import URLError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig


class PlayerInstance:
    """Manage the standalone desktop player process."""

    def __init__(self):
        self.player_process: Optional[subprocess.Popen] = None
        player_dir = Path(__file__).parent.parent / "player"
        self.player_script_path = player_dir / "modern_player.py"
        self.player_log_path = AppConfig().DATA_DIR / "player.log"
        self._lock = threading.Lock()
        self._last_play_time = 0.0
        self._play_cooldown = 2.0
        self.current_context: dict = {}
        self._control_port: Optional[int] = None

    def play(
        self,
        url: str,
        position: int = 0,
        title: str = "",
        headers: Optional[dict] = None,
        context: Optional[dict] = None,
        allow_rapid: bool = False,
    ) -> bool:
        """Start the standalone player with a local path or stream URL."""
        with self._lock:
            now = time.time()
            if not allow_rapid and now - self._last_play_time < self._play_cooldown:
                logger.warning("Play request ignored because it is still in cooldown")
                return False

            try:
                if self.player_process and self.player_process.poll() is None:
                    logger.info("Existing player process detected; terminating it first")
                    try:
                        self.player_process.terminate()
                        self.player_process.wait(timeout=3)
                    except Exception as exc:
                        logger.warning("Failed to terminate existing player process: %s", exc)
                        try:
                            self.player_process.kill()
                        except Exception:
                            pass

                if not getattr(sys, "frozen", False) and not self.player_script_path.exists():
                    logger.error("Player script does not exist: %s", self.player_script_path)
                    return False

                logger.info("Build playback URL: %s", _safe_log_url(url))
                logger.info("Launch player command: %s <url>", sys.executable)

                self.player_log_path.parent.mkdir(parents=True, exist_ok=True)
                self._control_port = self._allocate_control_port()
                with open(self.player_log_path, "ab") as log_file:
                    log_file.write(b"\n========== player start ==========\n")
                    self.player_process = self._start_process(
                        self.player_script_path,
                        url,
                        headers or {},
                        title or "",
                        max(0, int(position or 0)),
                        self._control_port,
                        context or {},
                        log_file,
                    )

                time.sleep(1.0)
                if self.player_process.poll() is not None:
                    logger.error(
                        "Player process exited immediately, return code: %s",
                        self.player_process.returncode,
                    )
                    logger.error("Player log: %s", self.player_log_path)
                    return False

                self._last_play_time = now
                self.current_context = dict(context or {})
                self.current_context.update({
                    "url": url,
                    "position": max(0, int(position or 0)),
                    "title": title or "",
                    "headers": headers or {},
                })
                logger.info("Player started: %s", title or url)
                return True
            except Exception as exc:
                logger.error("Failed to start player: %s", exc, exc_info=True)
                return False

    def switch_source(
        self,
        url: str,
        position: int = 0,
        title: str = "",
        headers: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> bool:
        """Switch the existing player window to another source."""
        with self._lock:
            if not self.is_running() or not self._control_port:
                return False

            payload = {
                "url": url,
                "position": max(0, int(position or 0)),
                "title": title or "",
                "headers": headers or {},
                "context": context or {},
            }
            try:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urlrequest.Request(
                    f"http://127.0.0.1:{self._control_port}/load",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlrequest.urlopen(req, timeout=2.5) as response:
                    if response.status != 200:
                        return False
            except (OSError, URLError, TimeoutError, ValueError) as exc:
                logger.warning("Player source switch command failed: %s", exc)
                return False

            self._last_play_time = time.time()
            self.current_context = dict(context or {})
            self.current_context.update({
                "url": url,
                "position": max(0, int(position or 0)),
                "title": title or "",
                "headers": headers or {},
            })
            logger.info("Player switched source: %s", title or url)
            return True

    @staticmethod
    def _allocate_control_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _start_process(self, script_path: Path, url: str, headers: dict, title: str, position: int, control_port: int, context: dict, log_file) -> subprocess.Popen:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        player_args = [
            url,
            json.dumps(headers or {}, ensure_ascii=False),
            title or "",
            str(max(0, int(position or 0))),
            str(int(control_port or 0)),
            json.dumps(context or {}, ensure_ascii=False),
        ]
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--player", *player_args]
        else:
            cmd = [sys.executable, str(script_path), *player_args]
        return subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )

    def stop(self) -> bool:
        """Stop the standalone player process if it is still running."""
        try:
            if self.player_process and self.player_process.poll() is None:
                self.player_process.terminate()
                try:
                    self.player_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.player_process.kill()
                    self.player_process.wait(timeout=2)
                logger.info("Player stopped")
                self.player_process = None
                self.current_context = {}
                self._control_port = None
                return True
            self.player_process = None
            self.current_context = {}
            self._control_port = None
            return False
        except Exception as exc:
            logger.error("Failed to stop player: %s", exc)
            try:
                if self.player_process and self.player_process.poll() is None:
                    self.player_process.kill()
            except Exception:
                pass
            self.player_process = None
            self.current_context = {}
            self._control_port = None
            return False

    def is_running(self) -> bool:
        """Return whether the standalone player process is alive."""
        if self.player_process is None:
            return False
        if self.player_process.poll() is None:
            return True
        self.player_process = None
        self._control_port = None
        return False


_player_instance: Optional[PlayerInstance] = None


def _safe_log_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if parsed.scheme in {"http", "https"} and parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?<redacted>"
    return str(url or "")


def get_player() -> PlayerInstance:
    """Return the global player process manager."""
    global _player_instance
    if _player_instance is None:
        _player_instance = PlayerInstance()
    return _player_instance
