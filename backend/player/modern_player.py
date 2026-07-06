from __future__ import annotations

import json
import logging
import math
import os
import sys
import threading
import time
import ctypes
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

PLAYER_DIR = Path(__file__).resolve().parent
os.environ["PATH"] = str(PLAYER_DIR) + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("QT_OPENGL", "desktop")

import mpv  # noqa: E402

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QOpenGLContext,
    QPainter,
    QPainterPath,
    QPen,
    QSurfaceFormat,
    QWheelEvent,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QMessageBox


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SW_RESTORE = 9
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _format_clock(seconds: float) -> str:
    if seconds is None or seconds <= 0:
        return "00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _normalize_track_id(value: Any) -> Optional[int]:
    if value in (None, "", "no", "auto"):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _language_name(value: str) -> str:
    lang = (value or "").strip().lower()
    aliases = {
        "zh": "中文",
        "zho": "中文",
        "chi": "中文",
        "chs": "简中",
        "cht": "繁中",
        "sc": "简中",
        "tc": "繁中",
        "cn": "中文",
        "ja": "日语",
        "jpn": "日语",
        "jp": "日语",
        "en": "英语",
        "eng": "英语",
        "ko": "韩语",
        "kor": "韩语",
        "kr": "韩语",
        "fr": "法语",
        "fre": "法语",
        "fra": "法语",
        "de": "德语",
        "ger": "德语",
        "deu": "德语",
        "es": "西语",
        "spa": "西语",
    }
    return aliases.get(lang, value.upper() if value else "")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class ModernMpvPlayer(QOpenGLWidget):
    frame_ready = Signal()
    file_loaded_signal = Signal()
    end_file_signal = Signal(str)
    load_source_signal = Signal(object)

    def __init__(
        self,
        video_path: str,
        headers: Optional[dict] = None,
        title: str = "",
        start_position: int = 0,
        control_port: int = 0,
        playback_context: Optional[dict] = None,
    ):
        super().__init__()
        self.video_path = video_path
        self.headers = headers or {}
        self.title_text = title or os.path.basename(video_path) or "JMH-MoviePop"
        self.start_position = max(0, int(start_position or 0))
        self._initial_seek_done = self.start_position <= 0
        self.playback_context = playback_context or {}
        self.playback_movie_id, self.playback_episode_id, self.playback_api_base = self._resolve_playback_target(
            video_path,
            self.playback_context,
        )
        self._next_progress_report = time.monotonic() + 5.0
        self._last_reported_second = -1
        self._progress_report_inflight = False
        self._last_watch_tick = time.monotonic()
        self._pending_watch_seconds = 0.0

        self.player: Optional[mpv.MPV] = None
        self.render_context: Optional[mpv.MpvRenderContext] = None
        self._get_proc_address_cb = None
        self.control_port = max(0, int(control_port or 0))
        self._control_server: Optional[ThreadingHTTPServer] = None
        self._control_thread: Optional[threading.Thread] = None
        self._display_awake = False

        self.file_loaded = False
        self.playback_finished = False
        self.loading_started_at = time.monotonic()
        self.loading_percent = 0
        self.position = 0.0
        self.duration = 0.0
        self.paused = False
        self.buffering = True
        self.volume = 80
        self.muted = False
        self.speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        self.speed_index = 2
        self.enhancement_profiles = [
            {
                "label": "原画",
                "options": None,
                "shaders": [],
            },
            {
                "label": "净化",
                "shaders": [],
                "options": {
                    "scale": "spline36",
                    "cscale": "spline36",
                    "dscale": "mitchell",
                    "scale-antiring": "0.55",
                    "correct-downscaling": "yes",
                    "linear-downscaling": "yes",
                    "sigmoid-upscaling": "yes",
                    "deband": "yes",
                    "deband-iterations": "1",
                    "deband-threshold": "32",
                    "deband-range": "16",
                    "deband-grain": "24",
                    "sharpen": "0.12",
                },
            },
            {
                "label": "锐化",
                "shaders": [],
                "options": {
                    "scale": "ewa_lanczossharp",
                    "cscale": "spline36",
                    "dscale": "mitchell",
                    "scale-antiring": "0.70",
                    "correct-downscaling": "yes",
                    "linear-downscaling": "yes",
                    "sigmoid-upscaling": "yes",
                    "deband": "yes",
                    "deband-iterations": "1",
                    "deband-threshold": "28",
                    "deband-range": "16",
                    "deband-grain": "16",
                    "sharpen": "0.35",
                },
            },
            {
                "label": "高清",
                "shaders": [],
                "options": {
                    "scale": "ewa_lanczossharp",
                    "cscale": "ewa_lanczossoft",
                    "dscale": "mitchell",
                    "scale-antiring": "0.80",
                    "correct-downscaling": "yes",
                    "linear-downscaling": "yes",
                    "sigmoid-upscaling": "yes",
                    "deband": "yes",
                    "deband-iterations": "2",
                    "deband-threshold": "35",
                    "deband-range": "20",
                    "deband-grain": "18",
                    "sharpen": "0.24",
                },
            },
            {
                "label": "动漫轻",
                "options": {
                    "scale": "ewa_lanczossharp",
                    "cscale": "spline36",
                    "scale-antiring": "0.70",
                    "deband": "yes",
                    "deband-iterations": "1",
                    "deband-threshold": "24",
                    "deband-range": "16",
                    "deband-grain": "12",
                    "sharpen": "0",
                },
                "shaders": [
                    "anime4k/Anime4K_Clamp_Highlights.glsl",
                    "anime4k/Anime4K_Restore_CNN_S.glsl",
                    "anime4k/Anime4K_Upscale_CNN_x2_S.glsl",
                ],
            },
            {
                "label": "动漫强",
                "options": {
                    "scale": "ewa_lanczossharp",
                    "cscale": "spline36",
                    "scale-antiring": "0.80",
                    "deband": "yes",
                    "deband-iterations": "1",
                    "deband-threshold": "24",
                    "deband-range": "16",
                    "deband-grain": "10",
                    "sharpen": "0",
                },
                "shaders": [
                    "anime4k/Anime4K_Clamp_Highlights.glsl",
                    "anime4k/Anime4K_Restore_CNN_M.glsl",
                    "anime4k/Anime4K_Upscale_CNN_x2_M.glsl",
                ],
            },
            {
                "label": "通用超",
                "options": {
                    "scale": "ewa_lanczossharp",
                    "cscale": "spline36",
                    "scale-antiring": "0.70",
                    "deband": "yes",
                    "deband-iterations": "1",
                    "deband-threshold": "28",
                    "deband-range": "16",
                    "deband-grain": "14",
                    "sharpen": "0.10",
                },
                "shaders": [
                    "fsrcnnx/FSRCNNX_x2_8-0-4-1.glsl",
                ],
            },
            {
                "label": "高质超",
                "options": {
                    "scale": "ewa_lanczossharp",
                    "cscale": "spline36",
                    "scale-antiring": "0.80",
                    "deband": "yes",
                    "deband-iterations": "1",
                    "deband-threshold": "26",
                    "deband-range": "16",
                    "deband-grain": "10",
                    "sharpen": "0.08",
                },
                "shaders": [
                    "fsrcnnx/FSRCNNX_x2_16-0-4-1.glsl",
                ],
            },
        ]
        self.enhancement_index = 0
        self._enhancement_original_options: dict[str, Any] = {}
        self.frame_profiles = [
            {
                "label": "关闭",
                "options": None,
            },
            {
                "label": "自然",
                "options": {
                    "video-sync": "display-resample",
                    "interpolation": "yes",
                    "tscale": "oversample",
                },
            },
            {
                "label": "平滑",
                "options": {
                    "video-sync": "display-resample",
                    "interpolation": "yes",
                    "tscale": "linear",
                },
            },
            {
                "label": "运动",
                "options": {
                    "video-sync": "display-resample",
                    "interpolation": "yes",
                    "tscale": "catmull_rom",
                },
            },
            {
                "label": "AI补帧",
                "options": {
                    "video-sync": "display-resample",
                    "interpolation": "no",
                    "tscale": "oversample",
                },
                "vapoursynth_rife": True,
            },
        ]
        self.frame_index = 0
        self._frame_original_options: dict[str, Any] = {}
        self.audio_tracks: list[dict[str, Any]] = []
        self.subtitle_tracks: list[dict[str, Any]] = []
        self.selected_audio_id: Optional[int] = None
        self.selected_subtitle_id: Optional[int] = None
        self._next_track_refresh = 0.0

        self.controls_opacity = 1.0
        self.controls_target_opacity = 1.0
        self.menu_opacity = 0.0
        self.menu_target_opacity = 0.0
        self.hide_deadline = time.monotonic() + 3.0
        self.cursor_hidden = False
        self.button_rects: dict[str, QRectF] = {}
        self.button_hover_anim: dict[str, float] = {}
        self.button_press_anim: dict[str, float] = {}
        self.button_pop_anim: dict[str, float] = {}
        self.progress_rect = QRectF()
        self.volume_rect = QRectF()
        self.menu_rect = QRectF()
        self.menu_item_rects: list[tuple[str, Any, QRectF]] = []
        self.active_menu: Optional[str] = None
        self.menu_scroll_index = 0
        self.hover_button: Optional[str] = None
        self.hover_menu_key: Optional[str] = None
        self.pressed_button: Optional[str] = None
        self.pressed_menu_key: Optional[str] = None
        self.dragging_progress = False
        self.dragging_volume = False
        self.dragging_window = False
        self.drag_start_global = None
        self.drag_start_pos = None
        self.normal_geometry = None
        self.progress_hover = False
        self.volume_hover = False
        self.center_feedback = 0.0
        self.center_feedback_icon = "pause"
        self.always_on_top = False
        self._startup_topmost = False

        self.setWindowTitle("JMH-MoviePop")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint)
        self.resize(1280, 720)
        self.setMinimumSize(900, 520)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)

        self.frame_ready.connect(self.update)
        self.file_loaded_signal.connect(self._on_file_loaded)
        self.end_file_signal.connect(self._on_end_file)
        self.load_source_signal.connect(self._load_source)

        self._create_player()
        self._start_control_server()

        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._poll_state)
        self.state_timer.start(100)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._tick_ui)
        self.ui_timer.start(16)

    def _create_player(self) -> None:
        mpv_options = {
            "vo": "libmpv",
            "hwdec": os.environ.get("MOVIEPOP_MPV_HWDEC", "auto-copy"),
            "gpu_api": "opengl",
            "vd_lavc_dr": "no",
            "osc": False,
            "input_default_bindings": False,
            "sub_auto": "all",
            "sub_visibility": "yes",
            "slang": "zh,chi,zho,chs,cht,sc,tc,ja,jpn,en,eng",
            "alang": "ja,jpn,zh,chi,zho,chs,cht,sc,tc,en,eng",
            "force_window": "no",
            "keep_open": "yes",
            "ytdl": False,
            "user_agent": USER_AGENT,
            "force_seekable": "yes",
            "cache": "yes",
            "cache_secs": 90,
            "cache_pause": "yes",
            "cache_pause_initial": "no",
            "cache_pause_wait": 8,
            "demuxer_readahead_secs": 90,
            "demuxer_max_bytes": "256MiB",
            "demuxer_max_back_bytes": "64MiB",
            "log_handler": self._mpv_log_handler,
            "loglevel": "info",
        }
        if self.headers:
            mpv_options["http_header_fields"] = ",".join(
                f"{key}: {value}" for key, value in self.headers.items()
            )

        self.player = mpv.MPV(**mpv_options)
        self.player.volume = self.volume

        @self.player.event_callback("file-loaded")
        def _file_loaded(_event):
            self.file_loaded_signal.emit()

        @self.player.event_callback("end-file")
        def _end_file(event):
            self.end_file_signal.emit(str(event))

    def _start_control_server(self) -> None:
        if self.control_port <= 0:
            return

        owner = self

        class ControlHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/load":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    raw = self.rfile.read(max(0, length))
                    payload = json.loads(raw.decode("utf-8") or "{}")
                    if not isinstance(payload, dict) or not payload.get("url"):
                        raise ValueError("Missing playback URL")
                    owner.load_source_signal.emit(payload)
                    body = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    logger.warning("Invalid player control request: %s", exc)
                    self.send_error(400, str(exc))

            def log_message(self, _format: str, *args: Any) -> None:
                return

        try:
            self._control_server = ThreadingHTTPServer(("127.0.0.1", self.control_port), ControlHandler)
            self._control_thread = threading.Thread(
                target=self._control_server.serve_forever,
                name="moviepop-player-control",
                daemon=True,
            )
            self._control_thread.start()
            logger.info("Player control server listening on 127.0.0.1:%s", self.control_port)
        except Exception:
            logger.exception("Failed to start player control server")
            self._control_server = None
            self._control_thread = None

    def _load_source(self, payload: object) -> None:
        if self.player is None or not isinstance(payload, dict):
            return
        url = str(payload.get("url") or "").strip()
        if not url:
            return
        headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
        title = str(payload.get("title") or os.path.basename(url) or "JMH-MoviePop")
        try:
            position = max(0, int(float(payload.get("position") or 0)))
        except Exception:
            position = 0

        try:
            self._maybe_report_progress(time.monotonic(), force=True)
        except Exception:
            pass

        self.video_path = url
        self.headers = headers or {}
        self.title_text = title
        self.start_position = position
        self._initial_seek_done = position <= 0
        self.playback_context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        self.playback_movie_id, self.playback_episode_id, self.playback_api_base = self._resolve_playback_target(
            url,
            self.playback_context,
        )
        self._next_progress_report = time.monotonic() + 5.0
        self._last_reported_second = -1
        self._pending_watch_seconds = 0.0
        self._last_watch_tick = time.monotonic()

        self.file_loaded = False
        self.playback_finished = False
        self.loading_started_at = time.monotonic()
        self.loading_percent = 0
        self.position = 0.0
        self.duration = 0.0
        self.buffering = True
        self.audio_tracks = []
        self.subtitle_tracks = []
        self.selected_audio_id = None
        self.selected_subtitle_id = None
        self._close_menu()
        self.setWindowTitle(title)
        QGuiApplication.setApplicationDisplayName(title)

        header_fields = ",".join(f"{key}: {value}" for key, value in self.headers.items())
        try:
            self.player.command("set", "http-header-fields", header_fields)
        except Exception:
            logger.debug("Update mpv HTTP headers failed", exc_info=True)
        try:
            self.player.loadfile(url, "replace")
            self.player.pause = False
            self.paused = False
            self._set_display_awake(True)
            self._show_controls(3.2)
            logger.info("Player source loaded: %s", title)
        except Exception:
            logger.exception("Load player source failed")

    def _mpv_log_handler(self, level: str, component: str, message: str) -> None:
        message = (message or "").strip()
        if not message:
            return
        if level in {"fatal", "error"}:
            logger.error("[MPV] %s - %s", component, message)
        elif level == "warn":
            logger.warning("[MPV] %s - %s", component, message)
        else:
            logger.debug("[MPV] %s - %s", component, message)

    def _set_display_awake(self, active: bool) -> None:
        if os.name != "nt" or active == self._display_awake:
            return
        flags = ES_CONTINUOUS
        if active:
            flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        try:
            result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
            if result:
                self._display_awake = active
                logger.info("Display sleep prevention %s", "enabled" if active else "released")
            else:
                logger.warning("SetThreadExecutionState failed: active=%s", active)
        except Exception:
            logger.debug("SetThreadExecutionState unavailable", exc_info=True)

    def bring_to_front(self) -> None:
        self._startup_topmost = not self.always_on_top
        if self._startup_topmost:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

        if os.name != "nt":
            if self._startup_topmost:
                QTimer.singleShot(1200, self._release_startup_topmost)
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow.restype = wintypes.BOOL
            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            logger.debug("Bring player window to front failed", exc_info=True)
        if self._startup_topmost:
            QTimer.singleShot(1200, self._release_startup_topmost)

    def _release_startup_topmost(self) -> None:
        if self.always_on_top or not self._startup_topmost:
            return
        self._startup_topmost = False
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()
        self.raise_()
        self.activateWindow()
        if os.name != "nt":
            return
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                HWND_NOTOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
        except Exception:
            logger.debug("Release startup topmost failed", exc_info=True)

    def initializeGL(self) -> None:
        try:
            self._init_render_context()
            assert self.player is not None
            self.player.play(self.video_path)
            self.player.pause = False
            self._set_display_awake(True)
            logger.info("Modern player started: %s", self.title_text)
        except Exception as exc:
            logger.error("Modern player failed to initialize: %s", exc, exc_info=True)
            QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Player error", str(exc)))
            QTimer.singleShot(0, self.close)

    def _init_render_context(self) -> None:
        context = QOpenGLContext.currentContext()
        if context is None:
            raise RuntimeError("OpenGL context is not available")

        def get_proc_address(_ctx, name):
            current = QOpenGLContext.currentContext()
            if current is None:
                return 0
            try:
                pointer = current.getProcAddress(name)
            except TypeError:
                pointer = current.getProcAddress(bytes(name))
            if not pointer:
                return 0
            try:
                return int(pointer)
            except TypeError:
                try:
                    import shiboken6

                    return int(shiboken6.VoidPtr(pointer))
                except Exception:
                    logger.debug("Could not convert OpenGL function pointer: %r", pointer)
                    return 0

        self._get_proc_address_cb = mpv.MpvGlGetProcAddressFn(get_proc_address)
        assert self.player is not None
        self.render_context = mpv.MpvRenderContext(
            self.player,
            "opengl",
            opengl_init_params={"get_proc_address": self._get_proc_address_cb},
        )
        self.render_context.update_cb = lambda: self.frame_ready.emit()

    def paintGL(self) -> None:
        painter = QPainter(self)
        if self.render_context is None:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            painter.end()
            return

        try:
            painter.beginNativePainting()
            try:
                dpr = self.devicePixelRatioF()
                self.render_context.update()
                self.render_context.render(
                    opengl_fbo={
                        "fbo": int(self.defaultFramebufferObject()),
                        "w": int(self.width() * dpr),
                        "h": int(self.height() * dpr),
                        "internal_format": 0,
                    },
                    flip_y=True,
                )
                self.render_context.report_swap()
            except Exception as exc:
                logger.error("mpv render failed: %s", exc, exc_info=True)
            finally:
                painter.endNativePainting()
        except Exception as exc:
            logger.error("Qt native painting failed: %s", exc, exc_info=True)

        painter.setRenderHint(QPainter.Antialiasing, True)
        self._draw_overlays(painter)
        painter.end()

    def _draw_overlays(self, painter: QPainter) -> None:
        self.button_rects = {}
        self.menu_item_rects = []

        if self._show_loading_ring():
            self._draw_loading_ring(painter)

        self._draw_center_play_feedback(painter)

        if self.controls_opacity <= 0.01 and self.menu_opacity <= 0.01:
            return

        w = self.width()
        h = self.height()

        painter.save()
        painter.setOpacity(self.controls_opacity)

        self._draw_top_status(painter)

        gradient = QLinearGradient(0, h - 170, 0, h)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.52, QColor(0, 0, 0, 58))
        gradient.setColorAt(0.78, QColor(0, 0, 0, 112))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 186))
        painter.fillRect(QRectF(0, h - 170, w, 170), gradient)

        self._draw_progress(painter)
        self._draw_controls(painter)
        painter.restore()

        if self.menu_opacity > 0.01:
            painter.save()
            painter.setOpacity(self.menu_opacity)
            self._draw_track_menu(painter)
            painter.restore()

    def _draw_top_status(self, painter: QPainter) -> None:
        gradient = QLinearGradient(0, 0, 0, 96)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 118))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(0, 0, self.width(), 92), gradient)

        painter.save()
        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.setPen(QColor(255, 255, 255, 232))
        title = painter.fontMetrics().elidedText(self.title_text, Qt.ElideRight, max(180, self.width() - 280))
        painter.drawText(QRectF(17, 12, self.width() - 280, 22), Qt.AlignLeft | Qt.AlignVCenter, title)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(255, 255, 255, 126))
        state = "Buffering" if self.buffering else ("Paused" if self.paused else "Playing")
        painter.drawText(QRectF(18, 34, 180, 20), Qt.AlignLeft | Qt.AlignVCenter, state)
        self._draw_window_chrome(painter)
        painter.restore()

    def _draw_window_chrome(self, painter: QPainter) -> None:
        size = 30
        gap = 4
        right = self.width() - 10
        y = 5
        buttons = [
            ("win_close", "close"),
            ("win_max", "restore" if self.isMaximized() else "maximize"),
            ("win_min", "minimize"),
            ("win_pin", "pin"),
        ]
        for index, (name, icon) in enumerate(buttons):
            x = right - (index + 1) * size - index * gap
            rect = QRectF(x, y, size, 25)
            self.button_rects[name] = rect
            hovered = self.hover_button == name
            if hovered and name == "win_close":
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(232, 65, 65, 160))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
            if name == "win_pin" and self.always_on_top:
                color = QColor(80, 145, 255, 245 if hovered else 218)
            else:
                color = QColor(255, 255, 255, 245 if hovered else 188)
            self._draw_icon(painter, icon, rect.adjusted(5.5, 4.5, -5.5, -4.5), color)

    def _draw_center_play_feedback(self, painter: QPainter) -> None:
        opacity = max(self.center_feedback, 0.0)
        if self.paused:
            opacity = max(opacity, 0.88)
            icon = "play"
            scale = 1.0
        elif opacity > 0.01:
            icon = self.center_feedback_icon
            scale = 1.0 + (1.0 - opacity) * 0.24
        else:
            return

        size = 72 * scale
        rect = QRectF(
            self.width() / 2 - size / 2,
            self.height() / 2 - size / 2,
            size,
            size,
        )
        painter.save()
        painter.setOpacity(opacity)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 88 if self.paused else 42))
        painter.drawEllipse(rect.adjusted(-4, -4, 4, 4))
        self._draw_icon(painter, icon, rect.adjusted(20, 18, -20, -18), QColor(255, 255, 255, 245))
        painter.restore()

    def _draw_progress(self, painter: QPainter) -> None:
        w = self.width()
        h = self.height()
        y = h - 23
        left_text = _format_clock(self.position)
        right_text = _format_clock(self.duration)

        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        left_width = metrics.horizontalAdvance(left_text)
        right_width = metrics.horizontalAdvance(right_text)

        margin = 20
        progress_x = margin + left_width + 14
        progress_w = max(120, w - progress_x - right_width - margin - 14)
        self.progress_rect = QRectF(progress_x, y - 10, progress_w, 20)

        line_width = 3.0 if self.progress_hover or self.dragging_progress else 2.0
        knob_radius = 5.5 if self.progress_hover or self.dragging_progress else 3.8

        painter.setPen(QPen(QColor(255, 255, 255, 76), line_width, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(progress_x, y), QPointF(progress_x + progress_w, y))

        ratio = 0.0 if self.duration <= 0 else _clamp(self.position / self.duration, 0.0, 1.0)
        played_x = progress_x + progress_w * ratio
        painter.setPen(QPen(QColor(66, 139, 255, 245), line_width, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(progress_x, y), QPointF(played_x, y))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.drawEllipse(QPointF(played_x, y), knob_radius, knob_radius)

        painter.setPen(QColor(255, 255, 255, 230))
        text_y = y + 4
        painter.drawText(QRectF(margin, text_y - 14, left_width + 2, 18), Qt.AlignLeft, left_text)
        painter.drawText(
            QRectF(w - margin - right_width - 2, text_y - 14, right_width + 2, 18),
            Qt.AlignRight,
            right_text,
        )

    def _draw_controls(self, painter: QPainter) -> None:
        w = self.width()
        h = self.height()
        y = h - 64
        icon_size = 32

        left_x = 25
        self._draw_icon_button(painter, "volume", "volume_muted" if self.muted else "volume", left_x, y, icon_size)
        volume_meter_x = left_x + 44
        self._draw_volume_meter(painter, volume_meter_x, y, 84, icon_size)
        speed_x = volume_meter_x + 144
        quality_x = speed_x + 60
        frame_x = quality_x + 92
        self._draw_text_button(painter, "speed", f"{self.speeds[self.speed_index]:.1f}x", speed_x, y, 52, icon_size)
        self._draw_text_button(painter, "quality", self._enhancement_label(), quality_x, y - 1, 84, icon_size + 2, font_size=10)
        self._draw_text_button(painter, "frame", self._frame_interpolation_label(), frame_x, y - 1, 72, icon_size + 2, font_size=10)

        center_total = 38 + 30 + 48 + 30 + 38
        left_controls_right = frame_x + 72
        center_x = max((w - center_total) / 2, left_controls_right + 24)
        self._draw_icon_button(painter, "previous", "previous", center_x, y, 38)
        self._draw_icon_button(painter, "play", "play" if self.paused else "pause", center_x + 68, y - 5, 48)
        self._draw_icon_button(painter, "next", "next", center_x + 146, y, 38)

        right_total = 38 * 3 + 18 * 2
        right_x = w - 25 - right_total
        self._draw_icon_button(painter, "subtitle", "subtitle", right_x, y, 38)
        self._draw_icon_button(painter, "audio", "audio", right_x + 56, y, 38)
        self._draw_icon_button(painter, "fullscreen", "fullscreen", right_x + 112, y, 38)

    def _draw_volume_meter(self, painter: QPainter, x: float, y: float, width: float, height: float) -> None:
        effective_volume = 0 if self.muted else int(_clamp(self.volume, 0, 100))
        ratio = effective_volume / 100.0
        center_y = y + height / 2
        track_h = 5.0
        track_rect = QRectF(x, center_y - track_h / 2, width, track_h)
        self.volume_rect = track_rect.adjusted(0, -9, 0, 9)

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 58 if self.volume_hover or self.dragging_volume else 42))
        painter.drawRoundedRect(track_rect, track_h / 2, track_h / 2)

        if ratio > 0:
            fill_rect = QRectF(track_rect.left(), track_rect.top(), track_rect.width() * ratio, track_rect.height())
            painter.setBrush(QColor(54, 112, 225, 238))
            painter.drawRoundedRect(fill_rect, track_h / 2, track_h / 2)

        knob_alpha = 245 if self.volume_hover or self.dragging_volume else 0
        if knob_alpha:
            knob_x = track_rect.left() + track_rect.width() * ratio
            painter.setBrush(QColor(255, 255, 255, knob_alpha))
            painter.drawEllipse(QPointF(knob_x, center_y), 4.2, 4.2)

        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        painter.setPen(QColor(255, 255, 255, 238))
        painter.drawText(QRectF(x + width + 10, y, 42, height), Qt.AlignLeft | Qt.AlignVCenter, f"{effective_volume:03d}%")
        painter.restore()

    def _draw_text_button(
        self,
        painter: QPainter,
        name: str,
        text: str,
        x: float,
        y: float,
        width: float,
        height: float,
        font_size: int = 8,
    ) -> None:
        rect = QRectF(x, y, width, height)
        self.button_rects[name] = rect
        hovered = self.hover_button == name
        hover = self.button_hover_anim.get(name, 0.0)
        press = self.button_press_anim.get(name, 0.0)
        pop = self.button_pop_anim.get(name, 0.0)
        pop_bounce = math.sin(pop * math.pi) * pop
        scale = 1.0 + hover * 0.055 + pop_bounce * 0.11 - press * 0.045
        painter.save()
        painter.translate(rect.center())
        painter.scale(scale, scale)
        draw_rect = QRectF(-rect.width() / 2, -rect.height() / 2, rect.width(), rect.height())
        draw_rect.translate(0, -1.4 * hover + 0.9 * press)
        painter.setFont(QFont("Segoe UI", font_size, QFont.DemiBold if font_size >= 10 else QFont.Normal))
        if hovered:
            painter.setPen(QColor(255, 255, 255, 255))
        else:
            painter.setPen(QColor(255, 255, 255, 205 + int(28 * hover)))
        painter.drawText(draw_rect, Qt.AlignCenter, text)
        painter.restore()

    def _draw_icon_button(self, painter: QPainter, name: str, icon: str, x: float, y: float, size: float) -> None:
        rect = QRectF(x, y, size, size)
        self.button_rects[name] = rect.adjusted(-4, -4, 4, 4)
        hovered = self.hover_button == name
        hover = self.button_hover_anim.get(name, 0.0)
        press = self.button_press_anim.get(name, 0.0)
        pop = self.button_pop_anim.get(name, 0.0)
        pop_bounce = math.sin(pop * math.pi) * pop
        scale = 1.0 + hover * 0.13 + pop_bounce * 0.18 - press * 0.075
        alpha = int(_clamp(218 + 37 * hover + 22 * pop_bounce, 0, 255))
        color = QColor(255, 255, 255, alpha)
        rect = self._scaled_rect(rect.translated(0, -1.6 * hover + 1.0 * press), scale)
        icon_rect = rect.adjusted(4.5, 4.5, -4.5, -4.5)
        if name == "play":
            icon_rect = rect.adjusted(5.0, 4.0, -5.0, -4.0)
        self._draw_icon(painter, icon, icon_rect, color)

    @staticmethod
    def _scaled_rect(rect: QRectF, scale: float) -> QRectF:
        center = rect.center()
        width = rect.width() * scale
        height = rect.height() * scale
        return QRectF(center.x() - width / 2, center.y() - height / 2, width, height)

    def _draw_icon(self, painter: QPainter, icon: str, rect: QRectF, color: QColor) -> None:
        painter.save()
        stroke = max(2.8, rect.width() * 0.13)
        pen = QPen(color, stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        def px(value: float) -> float:
            return rect.left() + rect.width() * value / 24.0

        def py(value: float) -> float:
            return rect.top() + rect.height() * value / 24.0

        def point(x: float, y: float) -> QPointF:
            return QPointF(px(x), py(y))

        def line(x1: float, y1: float, x2: float, y2: float) -> None:
            painter.drawLine(point(x1, y1), point(x2, y2))

        def fill_path(points: list[tuple[float, float]]) -> None:
            path = QPainterPath()
            first = points[0]
            path.moveTo(point(first[0], first[1]))
            for x, y in points[1:]:
                path.lineTo(point(x, y))
            path.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPath(path)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

        def round_rect(x: float, y: float, width: float, height: float, radius: float, fill: bool = False) -> None:
            box = QRectF(px(x), py(y), rect.width() * width / 24.0, rect.height() * height / 24.0)
            if fill:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(box, radius, radius)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
            else:
                painter.drawRoundedRect(box, radius, radius)

        if icon == "play":
            path = QPainterPath()
            path.moveTo(point(7.1, 4.9))
            path.quadTo(point(7.1, 3.7), point(8.5, 4.55))
            path.lineTo(point(19.4, 10.9))
            path.quadTo(point(21.2, 12.0), point(19.4, 13.1))
            path.lineTo(point(8.5, 19.45))
            path.quadTo(point(7.1, 20.3), point(7.1, 19.1))
            path.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPath(path)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
        elif icon == "pause":
            round_rect(7.1, 4.3, 4.4, 15.4, 2.0, fill=True)
            round_rect(12.5, 4.3, 4.4, 15.4, 2.0, fill=True)
        elif icon in {"previous", "next"}:
            if icon == "previous":
                round_rect(4.7, 5.1, 3.0, 13.8, 1.5, fill=True)
                fill_path([(18.8, 4.9), (8.8, 12.0), (18.8, 19.1)])
            else:
                round_rect(16.3, 5.1, 3.0, 13.8, 1.5, fill=True)
                fill_path([(5.2, 4.9), (15.2, 12.0), (5.2, 19.1)])
        elif icon in {"volume", "volume_muted"}:
            body = QPainterPath()
            body.moveTo(point(3.9, 9.0))
            body.lineTo(point(7.1, 9.0))
            body.lineTo(point(12.6, 4.7))
            body.quadTo(point(14.0, 3.8), point(14.0, 5.7))
            body.lineTo(point(14.0, 18.3))
            body.quadTo(point(14.0, 20.2), point(12.6, 19.3))
            body.lineTo(point(7.1, 15.0))
            body.lineTo(point(3.9, 15.0))
            body.quadTo(point(3.0, 15.0), point(3.0, 14.1))
            body.lineTo(point(3.0, 9.9))
            body.quadTo(point(3.0, 9.0), point(3.9, 9.0))
            body.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPath(body)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            if icon == "volume_muted":
                line(17.0, 8.7, 21.2, 15.3)
                line(21.2, 8.7, 17.0, 15.3)
            else:
                painter.setPen(QPen(color, stroke * 0.72, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawArc(QRectF(px(15.0), py(8.1), rect.width() * 4.3 / 24.0, rect.height() * 7.8 / 24.0), -43 * 16, 86 * 16)
                painter.drawArc(QRectF(px(15.2), py(5.6), rect.width() * 7.4 / 24.0, rect.height() * 12.8 / 24.0), -43 * 16, 86 * 16)
                painter.setPen(pen)
        elif icon == "subtitle":
            round_rect(3.3, 5.2, 17.4, 13.6, 3.4, fill=True)
            painter.setPen(QPen(QColor(0, 0, 0, 170), max(1.8, stroke * 0.45), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            line(7.0, 11.0, 11.4, 11.0)
            line(13.0, 11.0, 17.0, 11.0)
            line(7.1, 14.6, 16.9, 14.6)
            painter.setPen(pen)
        elif icon == "audio":
            for x, top, bottom, width in (
                (4.6, 9.4, 14.6, 2.5),
                (8.4, 6.8, 17.2, 2.5),
                (12.2, 8.3, 15.7, 2.5),
                (16.0, 5.2, 18.8, 2.5),
                (19.8, 9.1, 14.9, 2.5),
            ):
                round_rect(x - width / 2, top, width, bottom - top, width / 2, fill=True)
        elif icon == "search":
            painter.drawEllipse(QRectF(px(4.8), py(4.8), rect.width() * 10.5 / 24.0, rect.height() * 10.5 / 24.0))
            line(14.1, 14.1, 19.2, 19.2)
        elif icon == "pin":
            round_rect(7.0, 3.9, 10.0, 3.8, 1.9, fill=True)
            pin = QPainterPath()
            pin.moveTo(point(9.0, 7.2))
            pin.lineTo(point(15.0, 7.2))
            pin.lineTo(point(16.0, 12.4))
            pin.lineTo(point(18.6, 15.1))
            pin.quadTo(point(19.2, 15.8), point(18.2, 16.6))
            pin.lineTo(point(13.4, 16.6))
            pin.lineTo(point(12.4, 21.0))
            pin.quadTo(point(12.0, 22.0), point(11.6, 21.0))
            pin.lineTo(point(10.6, 16.6))
            pin.lineTo(point(5.8, 16.6))
            pin.quadTo(point(4.8, 15.8), point(5.4, 15.1))
            pin.lineTo(point(8.0, 12.4))
            pin.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPath(pin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
        elif icon == "minimize":
            round_rect(5.2, 14.1, 13.6, 2.8, 1.4, fill=True)
        elif icon == "maximize":
            round_rect(5.2, 5.2, 13.6, 13.6, 3.0, fill=True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.drawRoundedRect(QRectF(px(8.0), py(8.0), rect.width() * 8.0 / 24.0, rect.height() * 8.0 / 24.0), 1.5, 1.5)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(pen)
        elif icon == "restore":
            round_rect(8.0, 4.8, 10.8, 10.8, 2.3, fill=True)
            round_rect(5.2, 8.0, 10.8, 10.8, 2.3, fill=True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.drawRoundedRect(QRectF(px(8.0), py(10.8), rect.width() * 5.2 / 24.0, rect.height() * 5.2 / 24.0), 1.2, 1.2)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(pen)
        elif icon == "close":
            line(7.0, 7.0, 17.0, 17.0)
            line(17.0, 7.0, 7.0, 17.0)
        elif icon == "fullscreen":
            round_rect(4.8, 5.0, 2.8, 7.0, 1.4, fill=True)
            round_rect(4.8, 5.0, 7.0, 2.8, 1.4, fill=True)
            round_rect(16.4, 5.0, 2.8, 7.0, 1.4, fill=True)
            round_rect(12.2, 5.0, 7.0, 2.8, 1.4, fill=True)
            round_rect(4.8, 12.0, 2.8, 7.0, 1.4, fill=True)
            round_rect(4.8, 16.2, 7.0, 2.8, 1.4, fill=True)
            round_rect(16.4, 12.0, 2.8, 7.0, 1.4, fill=True)
            round_rect(12.2, 16.2, 7.0, 2.8, 1.4, fill=True)
        painter.restore()

    def _build_track_menu_items(self) -> list[dict[str, Any]]:
        if self.active_menu == "audio":
            if not self.audio_tracks:
                return [{"key": "audio:empty", "label": "无音轨", "id": None, "selected": False, "enabled": False}]
            return [
                {
                    "key": f"audio:{track['id']}",
                    "label": track["label"],
                    "id": track["id"],
                    "selected": track["id"] == self.selected_audio_id,
                    "enabled": True,
                }
                for track in self.audio_tracks
            ]

        if self.active_menu == "subtitle":
            items = [
                {
                    "key": "subtitle:none",
                    "label": "关闭",
                    "id": None,
                    "selected": self.selected_subtitle_id is None,
                    "enabled": True,
                }
            ]
            items.extend(
                {
                    "key": f"subtitle:{track['id']}",
                    "label": track["label"],
                    "id": track["id"],
                    "selected": track["id"] == self.selected_subtitle_id,
                    "enabled": True,
                }
                for track in self.subtitle_tracks
            )
            return items

        if self.active_menu == "quality":
            return [
                {
                    "key": f"quality:{index}",
                    "label": str(profile.get("label") or f"增强{index + 1}"),
                    "id": index,
                    "selected": index == self.enhancement_index,
                    "enabled": True,
                }
                for index, profile in enumerate(self.enhancement_profiles)
            ]

        if self.active_menu == "frame":
            return [
                {
                    "key": f"frame:{index}",
                    "label": str(profile.get("label") or f"补帧{index + 1}"),
                    "id": index,
                    "selected": index == self.frame_index,
                    "enabled": True,
                }
                for index, profile in enumerate(self.frame_profiles)
            ]

        return []

    def _draw_track_menu(self, painter: QPainter) -> None:
        if self.active_menu not in {"audio", "subtitle", "quality", "frame"}:
            self.menu_rect = QRectF()
            return

        items = self._build_track_menu_items()
        anchor = self.button_rects.get(self.active_menu)
        if anchor is None:
            anchor = QRectF(self.width() - 120, self.height() - 40, 34, 34)

        title = "音轨" if self.active_menu == "audio" else "字幕"
        width = 190 if self.active_menu == "audio" else 220
        title = {"audio": "音轨", "subtitle": "字幕", "quality": "画质增强"}.get(self.active_menu, title)
        title = {"audio": "音轨", "subtitle": "字幕", "quality": "画质增强", "frame": "补帧"}.get(self.active_menu, title)
        width = 190 if self.active_menu == "audio" else (168 if self.active_menu in {"quality", "frame"} else 220)
        title_h = 34
        search_h = 44 if self.active_menu == "subtitle" else 0
        row_h = 32
        visible_rows = max(1, min(6, len(items)))
        height = title_h + search_h + visible_rows * row_h + 12
        x = _clamp(anchor.center().x() - width / 2, 16, self.width() - width - 16)
        y = max(72, self.height() - 66 - height)
        self.menu_rect = QRectF(x, y, width, height)

        max_scroll = max(0, len(items) - visible_rows)
        self.menu_scroll_index = int(_clamp(self.menu_scroll_index, 0, max_scroll))
        visible = items[self.menu_scroll_index : self.menu_scroll_index + visible_rows]

        painter.save()
        shadow = QPainterPath()
        shadow.addRoundedRect(self.menu_rect.adjusted(-1, 4, 1, 8), 8, 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 72))
        painter.drawPath(shadow)

        body = QPainterPath()
        body.addRoundedRect(self.menu_rect, 7, 7)
        painter.setBrush(QColor(4, 4, 5, 226))
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1.0))
        painter.drawPath(body)

        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(QRectF(x + 14, y + 7, width - 28, 22), Qt.AlignLeft | Qt.AlignVCenter, title)
        painter.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
        painter.drawLine(QPointF(x, y + title_h), QPointF(x + width, y + title_h))

        row_y = y + title_h
        if self.active_menu == "subtitle":
            search_rect = QRectF(x + 12, row_y + 9, width - 48, 26)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 18))
            painter.drawRoundedRect(search_rect, 5, 5)
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(255, 255, 255, 88))
            painter.drawText(search_rect.adjusted(10, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, "未开启在线搜索")
            search_icon = QRectF(x + width - 38, row_y + 10, 24, 24)
            self._draw_icon(painter, "search", search_icon.adjusted(5, 5, -5, -5), QColor(255, 255, 255, 120))
            row_y += search_h

        self.menu_item_rects = []
        for item in visible:
            row = QRectF(x + 6, row_y, width - 12, row_h)
            self.menu_item_rects.append((item["key"], item, row))
            hovered = self.hover_menu_key == item["key"] and item.get("enabled", True)
            if hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, 22))
                painter.drawRoundedRect(row.adjusted(0, 2, 0, -2), 5, 5)

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor(255, 255, 255, 238 if item.get("enabled", True) else 92))
            if item.get("selected"):
                painter.setPen(QPen(QColor(255, 255, 255, 238), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                check_x = row.left() + 13
                check_y = row.center().y()
                painter.drawLine(QPointF(check_x, check_y), QPointF(check_x + 4, check_y + 4))
                painter.drawLine(QPointF(check_x + 4, check_y + 4), QPointF(check_x + 12, check_y - 6))
                painter.setFont(QFont("Segoe UI", 9))
                painter.setPen(QColor(255, 255, 255, 245))

            text_rect = row.adjusted(34, 0, -12, 0)
            label = painter.fontMetrics().elidedText(item["label"], Qt.ElideRight, int(text_rect.width()))
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, label)
            row_y += row_h

        if len(items) > visible_rows:
            bar_h = max(22, (visible_rows / len(items)) * (visible_rows * row_h - 4))
            bar_y = y + title_h + search_h + 2 + (self.menu_scroll_index / max_scroll) * (
                visible_rows * row_h - 4 - bar_h
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 80))
            painter.drawRoundedRect(QRectF(x + width - 7, bar_y, 3, bar_h), 1.5, 1.5)
        painter.restore()

    def _track_label(self, track: dict[str, Any], index: int, kind: str) -> str:
        title = _as_text(track.get("title")).strip()
        lang = _language_name(_as_text(track.get("lang")).strip())
        codec = _as_text(track.get("codec")).strip().upper()

        if title and lang and title.lower() != lang.lower():
            label = f"{lang} · {title}"
        elif title:
            label = title
        elif lang:
            label = lang
        else:
            label = f"{'音轨' if kind == 'audio' else '字幕'} {index}"

        if codec and codec not in label.upper():
            label = f"{label}  {codec}"
        return label

    def _refresh_track_list(self) -> None:
        player = self.player
        if player is None:
            return
        try:
            raw_tracks = getattr(player, "track_list", None) or []
        except Exception:
            raw_tracks = []
        if not isinstance(raw_tracks, list):
            raw_tracks = []

        audio: list[dict[str, Any]] = []
        subtitles: list[dict[str, Any]] = []
        try:
            selected_audio = _normalize_track_id(getattr(player, "aid", None))
        except Exception:
            selected_audio = None
        try:
            selected_subtitle = _normalize_track_id(getattr(player, "sid", None))
        except Exception:
            selected_subtitle = None

        for item in raw_tracks:
            if not isinstance(item, dict):
                continue
            track_type = _as_text(item.get("type")).lower()
            track_id = _normalize_track_id(item.get("id"))
            if track_id is None:
                continue
            selected = bool(item.get("selected"))
            if track_type == "audio":
                if selected:
                    selected_audio = track_id
                audio.append(
                    {
                        "id": track_id,
                        "label": self._track_label(item, len(audio) + 1, "audio"),
                        "selected": selected,
                    }
                )
            elif track_type in {"sub", "subtitle"}:
                if selected:
                    selected_subtitle = track_id
                subtitles.append(
                    {
                        "id": track_id,
                        "label": self._track_label(item, len(subtitles) + 1, "subtitle"),
                        "selected": selected,
                    }
                )

        self.audio_tracks = audio
        self.subtitle_tracks = subtitles
        self.selected_audio_id = selected_audio
        self.selected_subtitle_id = selected_subtitle

    def _show_loading_ring(self) -> bool:
        if not self.file_loaded:
            return True
        return self.buffering and not self.paused

    def _draw_loading_ring(self, painter: QPainter) -> None:
        painter.save()
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = 25
        rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        phase = (time.monotonic() * 190) % 360

        painter.setPen(QPen(QColor(255, 255, 255, 34), 3.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)
        for offset, alpha, span in ((0, 245, 38), (108, 188, 28), (214, 120, 22)):
            painter.setPen(QPen(QColor(42, 110, 235, alpha), 6.0, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(rect, int(-(phase + offset) * 16), int(-span * 16))
        painter.restore()

    @staticmethod
    def _parse_playback_target(video_path: str) -> tuple[str, str, str]:
        parsed = urlparse(str(video_path or ""))
        if not parsed.scheme or not parsed.netloc:
            return "", "", ""
        match = None
        parts = parsed.path.split("/")
        for index, part in enumerate(parts):
            if part == "movies" and index + 2 < len(parts) and parts[index + 2] == "stream":
                match = parts[index + 1]
                break
        if not match:
            return "", "", ""
        movie_id = unquote(match)
        query = parse_qs(parsed.query or "")
        episode_id = (query.get("episode_id") or [""])[0]
        return movie_id, episode_id, f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _resolve_playback_target(video_path: str, context: Optional[dict] = None) -> tuple[str, str, str]:
        fallback_movie_id, fallback_episode_id, fallback_api_base = ModernMpvPlayer._parse_playback_target(video_path)
        data = context or {}
        movie_id = str(data.get("movie_id") or data.get("movieId") or fallback_movie_id or "").strip()
        episode_id = str(data.get("episode_id") or data.get("episodeId") or fallback_episode_id or "").strip()
        api_base = str(data.get("api_base") or data.get("apiBase") or fallback_api_base or "").strip().rstrip("/")
        return movie_id, episode_id, api_base

    def _maybe_report_progress(self, now: float, force: bool = False) -> None:
        if not self.playback_movie_id or not self.playback_api_base:
            return
        if self.duration <= 0:
            return
        position = max(0, int(self.position or 0))
        if position <= 0 and not force:
            return
        if self._progress_report_inflight:
            return
        if not force and now < self._next_progress_report:
            return
        if not force and position == self._last_reported_second:
            return

        payload = {
            "episodeId": self.playback_episode_id,
            "currentTime": position,
            "duration": max(0, int(self.duration or 0)),
            "watchSecondsDelta": int(self._pending_watch_seconds),
        }
        self._pending_watch_seconds = max(0.0, self._pending_watch_seconds - int(self._pending_watch_seconds))
        self._last_reported_second = position
        self._next_progress_report = now + 10.0
        self._progress_report_inflight = True
        if force:
            self._post_progress(payload)
            return
        thread = threading.Thread(target=self._post_progress, args=(payload,), daemon=True)
        thread.start()

    def _post_progress(self, payload: dict[str, Any]) -> None:
        try:
            url = f"{self.playback_api_base}/api/movies/{quote(self.playback_movie_id, safe='')}/playback"
            requests.post(url, json=payload, timeout=1.5)
        except Exception:
            logger.debug("Playback progress report failed", exc_info=True)
        finally:
            self._progress_report_inflight = False

    def _poll_state(self) -> None:
        player = self.player
        if player is None:
            return
        try:
            self.position = float(getattr(player, "time_pos", 0) or 0)
            self.duration = float(getattr(player, "duration", 0) or 0)
            self.paused = bool(getattr(player, "pause", False))
            self.volume = int(float(getattr(player, "volume", self.volume) or 0))
            self.muted = bool(getattr(player, "mute", False))
            speed = float(getattr(player, "speed", self.speeds[self.speed_index]) or 1.0)
            self.speed_index = min(range(len(self.speeds)), key=lambda index: abs(self.speeds[index] - speed))

            cache_state = getattr(player, "cache_buffering_state", None)
            if cache_state is None:
                cache_value = 100 if self.file_loaded else 0
            else:
                cache_value = int(float(cache_state))

            if self.file_loaded:
                self.loading_percent = cache_value
                self.buffering = cache_value < 100 and not self.paused
            else:
                elapsed = time.monotonic() - self.loading_started_at
                synthetic = min(95, int(elapsed * 7))
                self.loading_percent = max(self.loading_percent, cache_value, synthetic)
                self.buffering = True
            now = time.monotonic()
            elapsed = max(0.0, min(1.0, now - self._last_watch_tick))
            self._last_watch_tick = now
            if self.file_loaded and not self.paused and not self.buffering and self.position > 0:
                self._pending_watch_seconds += elapsed * max(0.25, min(3.0, speed))
            if now >= self._next_track_refresh:
                self._next_track_refresh = now + 0.7
                self._refresh_track_list()
            self._set_display_awake(not self.playback_finished and not self.paused)
            self._maybe_report_progress(now)
        except Exception:
            pass

    def _tick_ui(self) -> None:
        now = time.monotonic()
        if self.active_menu:
            self.controls_target_opacity = 1.0
            self.menu_target_opacity = 1.0
            self.hide_deadline = now + 3.0
        else:
            self.menu_target_opacity = 0.0

        if not self.dragging_progress and not self.active_menu and now >= self.hide_deadline:
            self.controls_target_opacity = 0.0
        target = self.controls_target_opacity
        self.controls_opacity += (target - self.controls_opacity) * 0.18
        if abs(target - self.controls_opacity) < 0.01:
            self.controls_opacity = target

        self.menu_opacity += (self.menu_target_opacity - self.menu_opacity) * 0.22
        if abs(self.menu_target_opacity - self.menu_opacity) < 0.01:
            self.menu_opacity = self.menu_target_opacity

        self.center_feedback = max(0.0, self.center_feedback - 0.035)
        self._tick_button_animations()

        if self.controls_opacity <= 0.02 and not self.cursor_hidden:
            self.setCursor(Qt.BlankCursor)
            self.cursor_hidden = True
        elif self.controls_opacity > 0.02 and self.cursor_hidden:
            self.setCursor(Qt.ArrowCursor)
            self.cursor_hidden = False
        self.update()

    def _tick_button_animations(self) -> None:
        known_names = set(self.button_rects)
        known_names.update(self.button_hover_anim)
        known_names.update(self.button_press_anim)
        known_names.update(self.button_pop_anim)

        active_names = {self.hover_button} if self.hover_button else set()
        if self.active_menu:
            active_names.add(self.active_menu)
        if self.always_on_top:
            active_names.add("win_pin")

        for name in list(known_names):
            hover_target = 1.0 if name in active_names else 0.0
            press_target = 1.0 if name == self.pressed_button else 0.0

            hover_value = self.button_hover_anim.get(name, 0.0)
            press_value = self.button_press_anim.get(name, 0.0)
            pop_value = self.button_pop_anim.get(name, 0.0)

            hover_value += (hover_target - hover_value) * 0.26
            press_value += (press_target - press_value) * 0.38
            pop_value *= 0.72

            if hover_value < 0.01 and hover_target == 0.0:
                self.button_hover_anim.pop(name, None)
            else:
                self.button_hover_anim[name] = hover_value

            if press_value < 0.01 and press_target == 0.0:
                self.button_press_anim.pop(name, None)
            else:
                self.button_press_anim[name] = press_value

            if pop_value < 0.01:
                self.button_pop_anim.pop(name, None)
            else:
                self.button_pop_anim[name] = pop_value

    def _on_file_loaded(self) -> None:
        self.file_loaded = True
        self.playback_finished = False
        self.loading_percent = 100
        self.buffering = False
        if self.player is not None and self.start_position > 0 and not self._initial_seek_done:
            try:
                self.player.seek(self.start_position, "absolute", "exact")
                self.position = float(self.start_position)
                logger.info("Resumed playback at %ss", self.start_position)
            except Exception:
                logger.debug("Initial resume seek failed", exc_info=True)
            finally:
                self._initial_seek_done = True
        if self.player is not None and self.player.pause:
            self.player.pause = False
        QTimer.singleShot(160, self._ensure_initial_tracks)
        QTimer.singleShot(320, self._refresh_track_list)
        QTimer.singleShot(360, self._apply_enhancement_profile)
        QTimer.singleShot(380, self._apply_frame_interpolation_profile)
        logger.info("Video file loaded")

    def _ensure_initial_tracks(self) -> None:
        if self.player is None:
            return
        self._refresh_track_list()
        try:
            if self.subtitle_tracks and self.selected_subtitle_id is None:
                preferred = self.subtitle_tracks[0]["id"]
                self.player.sid = int(preferred)
                self.selected_subtitle_id = int(preferred)
                logger.info("Auto selected subtitle track: %s", preferred)
            if self.audio_tracks and self.selected_audio_id is None:
                preferred = self.audio_tracks[0]["id"]
                self.player.aid = int(preferred)
                self.selected_audio_id = int(preferred)
        except Exception:
            logger.debug("Initial track selection failed", exc_info=True)

    def _on_end_file(self, event: str) -> None:
        logger.info("Playback finished: %s", event)
        self.playback_finished = True
        self._set_display_awake(False)

    def _show_controls(self, seconds: float = 2.8) -> None:
        self.controls_target_opacity = 1.0
        self.hide_deadline = time.monotonic() + seconds
        if self.cursor_hidden:
            self.setCursor(Qt.ArrowCursor)
            self.cursor_hidden = False

    def _close_menu(self) -> None:
        self.active_menu = None
        self.hover_menu_key = None
        self.pressed_menu_key = None
        self.menu_target_opacity = 0.0

    def _menu_item_at(self, pos: QPointF) -> tuple[Optional[str], Optional[dict[str, Any]]]:
        if self.active_menu is None or self.menu_opacity < 0.05:
            return None, None
        for key, item, rect in self.menu_item_rects:
            if rect.contains(pos):
                if not item.get("enabled", True):
                    return key, None
                return key, item
        return None, None

    def _is_interactive_position(self, pos: QPointF) -> bool:
        if self.active_menu and self.menu_rect.contains(pos):
            return True
        if self.progress_rect.contains(pos):
            return True
        if self.volume_rect.contains(pos):
            return True
        if self._button_at(pos):
            return True
        return pos.y() >= self.height() - 155 and self.controls_opacity > 0.05

    def _is_title_drag_position(self, pos: QPointF) -> bool:
        return pos.y() <= 38 and self._button_at(pos) is None and not self.isFullScreen()

    def _button_at(self, pos: QPointF) -> Optional[str]:
        if self.controls_opacity < 0.05:
            return None
        for name, rect in self.button_rects.items():
            if rect.contains(pos):
                return name
        return None

    def _seek_from_position(self, x: float) -> None:
        if self.duration <= 0 or self.player is None or self.progress_rect.width() <= 0:
            return
        ratio = _clamp((x - self.progress_rect.left()) / self.progress_rect.width(), 0.0, 1.0)
        seconds = ratio * self.duration
        self.position = seconds
        try:
            self.player.seek(seconds, "absolute", "exact")
        except Exception:
            logger.debug("Seek failed", exc_info=True)

    def _set_volume_from_position(self, x: float) -> None:
        if self.player is None or self.volume_rect.width() <= 0:
            return
        ratio = _clamp((x - self.volume_rect.left()) / self.volume_rect.width(), 0.0, 1.0)
        self.volume = int(round(ratio * 100))
        try:
            self.player.volume = self.volume
            self.player.mute = self.volume <= 0
            self.muted = bool(self.player.mute)
        except Exception:
            logger.debug("Set volume from meter failed", exc_info=True)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if self.dragging_window and self.drag_start_global is not None and self.drag_start_pos is not None:
            global_pos = event.globalPosition().toPoint()
            self.move(self.drag_start_pos + (global_pos - self.drag_start_global))
            event.accept()
            return
        self._show_controls(3.0 if pos.y() > self.height() - 155 else 2.4)
        if self.dragging_progress:
            self._seek_from_position(pos.x())
        if self.dragging_volume:
            self._set_volume_from_position(pos.x())
        self.progress_hover = self.progress_rect.contains(pos)
        self.volume_hover = self.volume_rect.contains(pos)
        menu_key, _menu_item = self._menu_item_at(pos)
        if menu_key != self.hover_menu_key:
            self.hover_menu_key = menu_key
        new_hover = self._button_at(pos)
        if new_hover != self.hover_button:
            self.hover_button = new_hover
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position()
            self._show_controls()
            menu_key, menu_item = self._menu_item_at(pos)
            if self.active_menu and self.menu_rect.contains(pos):
                self.pressed_menu_key = menu_key if menu_item else None
                event.accept()
                return
            button_at_pos = self._button_at(pos)
            if self.active_menu and button_at_pos not in {"audio", "subtitle", "quality", "frame"}:
                self._close_menu()
            if button_at_pos:
                self.button_press_anim[button_at_pos] = 1.0
            if self._is_title_drag_position(pos):
                self.dragging_window = True
                self.drag_start_global = event.globalPosition().toPoint()
                self.drag_start_pos = self.frameGeometry().topLeft()
                event.accept()
                return
            if self.progress_rect.contains(pos) and self.duration > 0:
                self.dragging_progress = True
                self._seek_from_position(pos.x())
                event.accept()
                return
            if self.volume_rect.contains(pos):
                self.dragging_volume = True
                self._set_volume_from_position(pos.x())
                event.accept()
                return
            self.pressed_button = button_at_pos
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            if self.dragging_window:
                self.dragging_window = False
                self.drag_start_global = None
                self.drag_start_pos = None
                event.accept()
                return
            if self.dragging_progress:
                self.dragging_progress = False
                self._seek_from_position(event.position().x())
                event.accept()
                return
            if self.dragging_volume:
                self.dragging_volume = False
                self._set_volume_from_position(event.position().x())
                event.accept()
                return
            menu_key, menu_item = self._menu_item_at(event.position())
            if menu_item and menu_key == self.pressed_menu_key:
                self._select_track_from_menu(menu_item)
                self.pressed_menu_key = None
                event.accept()
                return
            self.pressed_menu_key = None
            button = self._button_at(event.position())
            if button and button == self.pressed_button:
                self.button_pop_anim[button] = 1.0
                self.button_press_anim.pop(button, None)
                self._activate_button(button)
                event.accept()
                self.pressed_button = None
                return
            if self.pressed_button:
                self.button_press_anim.pop(self.pressed_button, None)
            self.pressed_button = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            if event.position().y() <= 38:
                if not self._button_at(event.position()) and not self.isFullScreen():
                    self._toggle_maximized()
                event.accept()
                return
            if self._is_interactive_position(event.position()):
                event.accept()
                return
            self._toggle_fullscreen()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.player is None:
            return
        if self.active_menu and self.menu_rect.contains(event.position()):
            items = self._build_track_menu_items()
            visible_rows = max(1, min(6, len(items)))
            max_scroll = max(0, len(items) - visible_rows)
            if max_scroll > 0:
                step = -1 if event.angleDelta().y() > 0 else 1
                self.menu_scroll_index = int(_clamp(self.menu_scroll_index + step, 0, max_scroll))
                self._show_controls()
                self.update()
            event.accept()
            return
        delta = 5 if event.angleDelta().y() > 0 else -5
        self.volume = int(_clamp(self.volume + delta, 0, 100))
        try:
            self.player.volume = self.volume
            if self.volume > 0:
                self.player.mute = False
        except Exception:
            pass
        self._show_controls()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key_Space, Qt.Key_K):
            self._toggle_play()
            event.accept()
            return
        if key == Qt.Key_Left:
            self._seek_relative(-5)
            event.accept()
            return
        if key == Qt.Key_Right:
            self._seek_relative(5)
            event.accept()
            return
        if key == Qt.Key_Up:
            self._change_volume(5)
            event.accept()
            return
        if key == Qt.Key_Down:
            self._change_volume(-5)
            event.accept()
            return
        if key in (Qt.Key_F, Qt.Key_F11):
            self._toggle_fullscreen()
            event.accept()
            return
        if key == Qt.Key_E:
            self._cycle_enhancement()
            event.accept()
            return
        if key == Qt.Key_R:
            self._cycle_frame_interpolation()
            event.accept()
            return
        if key == Qt.Key_Escape and self.active_menu:
            self._close_menu()
            event.accept()
            return
        if key == Qt.Key_Escape and self.isFullScreen():
            self._toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_button = None
        self.hover_menu_key = None
        self.progress_hover = False
        self.volume_hover = False
        self.hide_deadline = min(self.hide_deadline, time.monotonic() + 0.8)
        super().leaveEvent(event)

    def _activate_button(self, name: str) -> None:
        actions = {
            "volume": self._toggle_mute,
            "speed": self._cycle_speed,
            "quality": lambda: self._toggle_track_menu("quality"),
            "frame": lambda: self._toggle_track_menu("frame"),
            "previous": lambda: self._playlist_command("playlist-prev"),
            "play": self._toggle_play,
            "next": lambda: self._playlist_command("playlist-next"),
            "subtitle": lambda: self._toggle_track_menu("subtitle"),
            "audio": lambda: self._toggle_track_menu("audio"),
            "fullscreen": self._toggle_fullscreen,
            "win_pin": self._toggle_always_on_top,
            "win_min": self.showMinimized,
            "win_max": self._toggle_maximized,
            "win_close": self.close,
        }
        action = actions.get(name)
        if action:
            action()
        self._show_controls()

    def _toggle_track_menu(self, menu_name: str) -> None:
        self._refresh_track_list()
        if self.active_menu == menu_name:
            self._close_menu()
            return
        self.active_menu = menu_name
        self.menu_scroll_index = 0
        self.hover_menu_key = None
        self.pressed_menu_key = None
        self.menu_target_opacity = 1.0
        self._show_controls(4.0)

    def _select_track_from_menu(self, item: dict[str, Any]) -> None:
        if self.active_menu == "frame":
            try:
                self.frame_index = int(item.get("id") or 0)
            except Exception:
                self.frame_index = 0
            self.frame_index = int(_clamp(self.frame_index, 0, len(self.frame_profiles) - 1))
            self._apply_frame_interpolation_profile()
            logger.info("Frame interpolation profile: %s", self._frame_interpolation_label())
            self._close_menu()
            self._show_controls(3.4)
            return
        if self.active_menu == "quality":
            try:
                self.enhancement_index = int(item.get("id") or 0)
            except Exception:
                self.enhancement_index = 0
            self.enhancement_index = int(_clamp(self.enhancement_index, 0, len(self.enhancement_profiles) - 1))
            self._apply_enhancement_profile()
            logger.info("Video enhancement profile: %s", self._enhancement_label())
            self._close_menu()
            self._show_controls(3.4)
            return
        if self.active_menu not in {"audio", "subtitle"} or self.player is None:
            return
        prop = "aid" if self.active_menu == "audio" else "sid"
        track_id = item.get("id")
        if prop == "aid" and track_id is None:
            return
        value: Any = "no" if track_id is None else int(track_id)
        try:
            if prop == "aid":
                self.player.aid = value
            else:
                self.player.sid = value
            if prop == "aid":
                self.selected_audio_id = _normalize_track_id(value)
            else:
                self.selected_subtitle_id = _normalize_track_id(value)
            logger.info("Selected %s track: %s", prop, value)
            QTimer.singleShot(120, self._refresh_track_list)
        except Exception:
            logger.debug("Select %s track failed", prop, exc_info=True)
        self._close_menu()
        self._show_controls()

    def _enhancement_label(self) -> str:
        try:
            return str(self.enhancement_profiles[self.enhancement_index]["label"])
        except Exception:
            return "原画"

    def _cycle_enhancement(self) -> None:
        if self.player is None:
            return
        self.enhancement_index = (self.enhancement_index + 1) % len(self.enhancement_profiles)
        self._apply_enhancement_profile()
        logger.info("Video enhancement profile: %s", self._enhancement_label())
        self._show_controls(3.4)

    def _apply_enhancement_profile(self) -> None:
        if self.player is None:
            return
        profile = self.enhancement_profiles[self.enhancement_index]
        options = profile.get("options")
        self._remember_original_enhancement_options()
        self._clear_enhancement_shaders()
        self._restore_original_enhancement_options()
        if not options:
            return
        for name, value in options.items():
            self._set_mpv_option(name, value)
        for shader in profile.get("shaders") or []:
            self._append_enhancement_shader(str(shader))

    def _remember_original_enhancement_options(self) -> None:
        if self.player is None or self._enhancement_original_options:
            return
        for name in (
            "scale",
            "cscale",
            "dscale",
            "scale-antiring",
            "correct-downscaling",
            "linear-downscaling",
            "sigmoid-upscaling",
            "deband",
            "deband-iterations",
            "deband-threshold",
            "deband-range",
            "deband-grain",
            "sharpen",
        ):
            try:
                self._enhancement_original_options[name] = getattr(self.player, name.replace("-", "_"))
            except Exception:
                self._enhancement_original_options[name] = None

    def _restore_original_enhancement_options(self) -> None:
        self._clear_enhancement_shaders()
        for name, value in self._enhancement_original_options.items():
            if value is not None:
                self._set_mpv_option(name, value)

    def _clear_enhancement_shaders(self) -> None:
        try:
            self.player.command("change-list", "glsl-shaders", "clr", "")
        except Exception:
            logger.debug("Clear GLSL shader list failed", exc_info=True)

    def _append_enhancement_shader(self, relative_path: str) -> None:
        if self.player is None:
            return
        shader_path = (PLAYER_DIR / "shaders" / relative_path).resolve()
        if not shader_path.exists():
            logger.warning("Enhancement shader missing: %s", shader_path)
            return
        try:
            self.player.command("change-list", "glsl-shaders", "append", str(shader_path))
        except Exception:
            logger.debug("Append GLSL shader failed: %s", shader_path, exc_info=True)

    def _frame_interpolation_label(self) -> str:
        try:
            return str(self.frame_profiles[self.frame_index]["label"])
        except Exception:
            return "关闭"

    def _cycle_frame_interpolation(self) -> None:
        if self.player is None:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frame_profiles)
        self._apply_frame_interpolation_profile()
        logger.info("Frame interpolation profile: %s", self._frame_interpolation_label())
        self._show_controls(3.4)

    def _apply_frame_interpolation_profile(self) -> None:
        if self.player is None:
            return
        profile = self.frame_profiles[self.frame_index]
        options = profile.get("options")
        self._remember_original_frame_options()
        self._remove_vapoursynth_rife_filter()
        self._restore_original_frame_options()
        if not options:
            return
        for name, value in options.items():
            self._set_mpv_option(name, value)
        if profile.get("vapoursynth_rife"):
            self._append_vapoursynth_rife_filter()

    def _remember_original_frame_options(self) -> None:
        if self.player is None or self._frame_original_options:
            return
        for name in (
            "video-sync",
            "interpolation",
            "tscale",
        ):
            try:
                self._frame_original_options[name] = getattr(self.player, name.replace("-", "_"))
            except Exception:
                self._frame_original_options[name] = None

    def _restore_original_frame_options(self) -> None:
        for name, value in self._frame_original_options.items():
            if value is not None:
                self._set_mpv_option(name, value)

    @staticmethod
    def _escape_mpv_filter_value(value: str) -> str:
        return (
            value.replace("\\", "/")
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace(";", "\\;")
        )

    def _remove_vapoursynth_rife_filter(self) -> None:
        if self.player is None:
            return
        try:
            self.player.command("vf", "remove", "@moviepop-rife")
        except Exception:
            logger.debug("Remove RIFE VapourSynth filter skipped", exc_info=True)

    def _append_vapoursynth_rife_filter(self) -> bool:
        if self.player is None:
            return False
        script_path = (PLAYER_DIR / "vapoursynth" / "rife_realtime.vpy").resolve()
        if not script_path.exists():
            logger.warning("RIFE VapourSynth script missing: %s", script_path)
            return False
        plugin_dir = PLAYER_DIR / "vapoursynth" / "plugins"
        plugin_path = plugin_dir / "librife_windows_x86-64.dll"
        model_root = plugin_dir / "models"
        if os.name == "nt" and not plugin_path.exists():
            logger.warning("RIFE VapourSynth plugin missing: %s", plugin_path)
            return False
        if not any((model_root / name).exists() for name in ("rife-v4_ensembleFalse_fastTrue", "rife-v2.3")):
            logger.warning("RIFE model files missing under: %s", model_root)
            return False
        filter_spec = f"@moviepop-rife:vapoursynth=file={self._escape_mpv_filter_value(str(script_path))}"
        try:
            self.player.command("vf", "add", filter_spec)
            return True
        except Exception:
            logger.warning(
                "RIFE VapourSynth filter failed. Install VapourSynth and VapourSynth-RIFE-ncnn-Vulkan to use AI补帧.",
                exc_info=True,
            )
            return False

    def _set_mpv_option(self, name: str, value: Any) -> None:
        if self.player is None:
            return
        try:
            if isinstance(value, bool):
                value = "yes" if value else "no"
            self.player.command("set", name, str(value))
        except Exception:
            logger.debug("Set mpv option failed: %s=%s", name, value, exc_info=True)

    def _noop(self) -> None:
        logger.info("Quality selector is not available for this stream")

    def _toggle_play(self) -> None:
        if self.player is None:
            return
        try:
            self.player.pause = not bool(self.player.pause)
            self.paused = bool(self.player.pause)
            self._set_display_awake(not self.paused and not self.playback_finished)
            self.center_feedback_icon = "play" if self.paused else "pause"
            self.center_feedback = 1.0
        except Exception:
            logger.debug("Toggle play failed", exc_info=True)

    def _toggle_mute(self) -> None:
        if self.player is None:
            return
        try:
            self.player.mute = not bool(getattr(self.player, "mute", False))
            self.muted = bool(self.player.mute)
        except Exception:
            logger.debug("Toggle mute failed", exc_info=True)

    def _change_volume(self, delta: int) -> None:
        if self.player is None:
            return
        self.volume = int(_clamp(self.volume + delta, 0, 100))
        try:
            self.player.volume = self.volume
            if self.volume > 0:
                self.player.mute = False
        except Exception:
            logger.debug("Change volume failed", exc_info=True)
        self._show_controls()

    def _cycle_speed(self) -> None:
        if self.player is None:
            return
        self.speed_index = (self.speed_index + 1) % len(self.speeds)
        try:
            self.player.speed = self.speeds[self.speed_index]
        except Exception:
            logger.debug("Cycle speed failed", exc_info=True)

    def _cycle_track(self, prop: str) -> None:
        if self.player is None:
            return
        try:
            self.player.command("cycle", prop)
        except Exception:
            logger.debug("Cycle %s failed", prop, exc_info=True)

    def _playlist_command(self, command: str) -> None:
        if not self.playback_api_base:
            return
        endpoint = "previous" if command == "playlist-prev" else "next"
        try:
            self._maybe_report_progress(time.monotonic(), force=True)
        except Exception:
            pass
        thread = threading.Thread(target=self._post_player_command, args=(endpoint,), daemon=True)
        thread.start()

    def _post_player_command(self, endpoint: str) -> None:
        try:
            requests.post(f"{self.playback_api_base}/api/player/{endpoint}", timeout=2.0)
        except Exception:
            logger.debug("Player %s command failed", endpoint, exc_info=True)

    def _seek_relative(self, seconds: float) -> None:
        if self.player is None:
            return
        try:
            self.player.seek(seconds, "relative", "exact")
        except Exception:
            logger.debug("Relative seek failed", exc_info=True)
        self._show_controls()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._show_controls()

    def _toggle_maximized(self) -> None:
        if self.isFullScreen():
            return
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._show_controls()

    def _toggle_always_on_top(self) -> None:
        self.always_on_top = not self.always_on_top
        was_fullscreen = self.isFullScreen()
        was_maximized = self.isMaximized()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        if was_fullscreen:
            self.showFullScreen()
        elif was_maximized:
            self.showMaximized()
        else:
            self.show()
        self._show_controls()

    def closeEvent(self, event) -> None:
        self._set_display_awake(False)
        try:
            self._maybe_report_progress(time.monotonic(), force=True)
        except Exception:
            pass
        try:
            self.state_timer.stop()
            self.ui_timer.stop()
        except Exception:
            pass
        try:
            if self._control_server is not None:
                self._control_server.shutdown()
                self._control_server.server_close()
                self._control_server = None
        except Exception:
            logger.debug("Stop player control server failed", exc_info=True)
        try:
            if self.render_context is not None:
                self.makeCurrent()
                self.render_context.update_cb = None
                self.render_context.free()
                self.render_context = None
                self.doneCurrent()
        except Exception:
            logger.debug("Free render context failed", exc_info=True)
        try:
            if self.player is not None:
                self.player.stop()
                self.player.terminate()
                self.player = None
        except Exception:
            logger.debug("Terminate mpv failed", exc_info=True)
        app = QApplication.instance()
        if app:
            QTimer.singleShot(0, app.quit)
        event.accept()


def _configure_surface() -> None:
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setVersion(2, 1)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(0)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python modern_player.py <video_path> [headers_json] [title]")
        return 1

    video_path = sys.argv[1]
    headers = {}
    if len(sys.argv) >= 3:
        try:
            parsed = json.loads(sys.argv[2])
            if isinstance(parsed, dict):
                headers = parsed
        except Exception as exc:
            logger.warning("Could not parse request headers: %s", exc)
    title = sys.argv[3] if len(sys.argv) >= 4 else ""
    try:
        start_position = int(float(sys.argv[4])) if len(sys.argv) >= 5 else 0
    except Exception:
        start_position = 0
    try:
        control_port = int(float(sys.argv[5])) if len(sys.argv) >= 6 else 0
    except Exception:
        control_port = 0
    try:
        playback_context = json.loads(sys.argv[6]) if len(sys.argv) >= 7 else {}
        if not isinstance(playback_context, dict):
            playback_context = {}
    except Exception:
        playback_context = {}

    _configure_surface()
    app = QApplication(sys.argv)
    QGuiApplication.setApplicationDisplayName(title or "JMH-MoviePop")

    try:
        player = ModernMpvPlayer(
            video_path,
            headers=headers,
            title=title,
            start_position=start_position,
            control_port=control_port,
            playback_context=playback_context,
        )
        player.show()
        QTimer.singleShot(0, player.bring_to_front)
        QTimer.singleShot(250, player.bring_to_front)
        return app.exec()
    except Exception as exc:
        logger.error("Modern player crashed during startup: %s", exc, exc_info=True)
        QMessageBox.critical(None, "Player error", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
