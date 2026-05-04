import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from backend.server import run_server, start_server_in_thread
from config.app_config import AppConfig
from utils.logger import get_logger


logger = get_logger()
logger.setLevel(logging.DEBUG)


def _kill_all_processes():
    """强制终止当前进程树中的所有进程"""
    import subprocess
    try:
        pid = os.getpid()
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
APP_ICON_PATH = str(BASE_DIR / "app.ico")


def show_error_message(title: str, message: str) -> None:
    print(f"{title}: {message}")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def global_exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    logger.critical("Unhandled exception: %s", error_msg)
    show_error_message("鸡米花启动失败", error_msg)
    sys.exit(1)


def wait_for_backend(url: str, timeout_seconds: float = 30.0) -> bool:
    try:
        import requests
    except ModuleNotFoundError:
        logger.exception("requests is missing")
        return False

    deadline = time.time() + timeout_seconds
    bootstrap_url = f"{url}/api/bootstrap"

    while time.time() < deadline:
        try:
            response = requests.get(bootstrap_url, timeout=1.5)
            if response.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.2)

    return False


def detect_webview_gui() -> str:
    edge_runtime_paths = (
        r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application",
        r"C:\Program Files\Microsoft\EdgeWebView\Application",
    )
    if any(os.path.isdir(path) for path in edge_runtime_paths):
        return "edgechromium"
    return "mshtml"


def run_webview_desktop(serve_frontend: str | None = None) -> None:
    try:
        import webview
    except ModuleNotFoundError as exc:
        logger.exception("pywebview is missing")
        raise RuntimeError(
            "未找到 pywebview，无法启动桌面窗口。请先安装依赖，或使用打包后的应用。"
        ) from exc

    logger.info("===== Starting native webview desktop shell =====")
    server, url, _, _thread = start_server_in_thread(serve_frontend=serve_frontend)

    if not wait_for_backend(url):
        server.should_exit = True
        raise RuntimeError("本地服务启动超时，未能打开鸡米花窗口。")

    window = webview.create_window(
        "鸡米花",
        url=url,
        width=1440,
        height=920,
        min_size=(1100, 720),
        resizable=True,
        background_color="#0f1720",
        text_select=True,
    )

    def shutdown():
        try:
            from core.openlist_manager import openlist_manager
            openlist_manager.stop()
        except Exception:
            pass
        try:
            server.should_exit = True
        except Exception:
            pass
        try:
            import threading
            def force_exit():
                time.sleep(1.5)
                _kill_all_processes()
            threading.Thread(target=force_exit, daemon=True).start()
        except Exception:
            pass

    window.events.closed += shutdown

    gui_backend = detect_webview_gui()
    logger.info("Starting webview with backend: %s", gui_backend)

    storage_path = os.path.join(AppConfig().BASE_DIR, "data", "webview")

    try:
        webview.start(
            gui=gui_backend,
            debug=False,
            private_mode=False,
            storage_path=storage_path,
        )
        return
    except Exception:
        if gui_backend == "mshtml":
            logger.exception("Native webview startup failed in mshtml mode")
            raise RuntimeError("桌面窗口启动失败，当前系统内核无法正常渲染应用界面。")

        logger.exception("Edge WebView2 startup failed, falling back to mshtml")
        try:
            webview.start(
                gui="mshtml",
                debug=False,
                private_mode=False,
                storage_path=storage_path,
            )
            return
        except Exception as exc:
            logger.exception("mshtml fallback failed")
            raise RuntimeError("桌面窗口启动失败，请检查 WebView2 运行时是否可用。") from exc


def main() -> None:
    sys.excepthook = global_exception_hook
    os.chdir(BASE_DIR)

    # 解析 --serve-frontend 参数
    serve_frontend = None
    for i, arg in enumerate(sys.argv):
        if arg == "--serve-frontend" and i + 1 < len(sys.argv):
            serve_frontend = sys.argv[i + 1]
            break

    if "--web-server" in sys.argv:
        logger.info("===== Starting standalone web server =====")
        run_server(
            open_browser="--no-browser" not in sys.argv,
            serve_frontend=serve_frontend,
        )
        return

    run_webview_desktop(serve_frontend=serve_frontend)


if __name__ == "__main__":
    main()
