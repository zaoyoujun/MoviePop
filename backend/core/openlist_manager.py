"""
OpenList 进程管理器
管理 OpenList 内置服务器的启动、停止、重启和健康检查
"""
import json
import logging
import os
import platform
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def _get_app_config_class():
    try:
        from backend.config import AppConfig
    except ImportError:
        from config import AppConfig
    return AppConfig

# 常量配置
OPENLIST_GITHUB_REPO = "OpenListTeam/OpenList"
OPENLIST_FALLBACK_VERSION = "v3.42.0"
OPENLIST_CHECK_URL = "http://127.0.0.1:{port}/api/public/settings"
OPENLIST_HEALTH_INTERVAL = 10  # 健康检查间隔（秒）
OPENLIST_MAX_RESTARTS = 3  # 最大重启次数
OPENLIST_PORT_RANGE = range(5244, 5265)  # 端口扫描范围
OPENLIST_DOWNLOAD_TIMEOUT = 300  # 下载总超时（秒）
OPENLIST_DOWNLOAD_CHUNK_SIZE = 8192
OPENLIST_MIRRORS = [
    "https://ghfast.top",
    "https://ghproxy.cn",
    "https://github.moeyy.xyz",
]


class OpenListManager:
    """OpenList 子进程管理器"""

    STATUS_STOPPED = "stopped"
    STATUS_STARTING = "starting"
    STATUS_RUNNING = "running"
    STATUS_ERROR = "error"
    STATUS_LOGGED_IN = "logged_in"  # 已登录状态

    def __init__(self, data_dir: Optional[Path] = None):
        AppConfig = _get_app_config_class()
        self._process: Optional[subprocess.Popen] = None
        self._status: str = self.STATUS_STOPPED
        self._error_message: str = ""
        self._lock = threading.Lock()
        self._health_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._restart_count: int = 0
        self._start_time: float = 0
        self._active_port: int = 0
        self._config = AppConfig()
        self._config.load_config()
        
        # 登录状态相关
        self._token: str = ""
        self._token_expires: float = 0
        self._logged_in: bool = False
        
        # 数据目录
        if data_dir is None:
            # 默认使用配置中的 DATA_DIR/openlist 目录
            self._data_dir = self._config.DATA_DIR / "openlist"
        else:
            self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
    
    def _kill_all_openlist_processes(self) -> None:
        """终止所有 openlist.exe 进程（防止重复启动）"""
        try:
            if platform.system() == "Windows":
                # 查找并终止所有 openlist.exe 进程
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq openlist.exe", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                output = result.stdout or ""
                for line in output.splitlines():
                    if "openlist.exe" in line.lower():
                        try:
                            parts = line.strip().split(",")
                            if len(parts) >= 2:
                                pid = parts[1].strip('"')
                                if pid.isdigit():
                                    subprocess.run(
                                        ["taskkill", "/F", "/T", "/PID", pid],
                                        capture_output=True, timeout=5,
                                        creationflags=subprocess.CREATE_NO_WINDOW,
                                    )
                                    logger.info(f"已终止旧的 openlist.exe 进程: PID={pid}")
                        except Exception as e:
                            logger.warning(f"终止进程失败: {e}")
            else:
                # Linux/macOS
                subprocess.run(
                    ["pkill", "-f", "openlist"],
                    capture_output=True, timeout=10,
                )
        except Exception as e:
            logger.warning(f"清理旧进程时出错: {e}")

    def get_binary_path(self) -> Path:
        """获取 OpenList 二进制文件路径"""
        ext = ".exe" if platform.system() == "Windows" else ""
        # 优先检查数据目录中的二进制文件
        data_path = self._data_dir / f"openlist{ext}"
        if data_path.is_file():
            return data_path
        # 检查 backend/openlist 目录（用户实际放置的位置）
        backend_path = Path(__file__).parent.parent / "openlist" / f"openlist{ext}"
        if backend_path.is_file():
            return backend_path
        # 检查 data/openlist 目录（另一个常见位置）
        data_openlist_path = self._config.DATA_DIR.parent / "openlist" / f"openlist{ext}"
        if data_openlist_path.is_file():
            return data_openlist_path
        # 返回默认路径
        return data_path

    def get_data_dir(self) -> Path:
        """获取数据目录"""
        return self._data_dir

    def is_binary_available(self) -> bool:
        """检查二进制文件是否存在"""
        return self.get_binary_path().is_file()

    def get_binary_version(self) -> Optional[str]:
        """获取 OpenList 版本号"""
        binary = self.get_binary_path()
        if not binary.is_file():
            return None
        try:
            result = subprocess.run(
                [str(binary), "version"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            output = (result.stdout or result.stderr or "").strip()
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("v") or line.startswith("Version"):
                    return line.split()[-1].strip()
            return output.splitlines()[0].strip() if output else None
        except Exception as e:
            logger.error(f"获取版本失败: {e}")
            return None

    def _find_available_port(self) -> int:
        """查找可用端口"""
        preferred = self._config.OPENLIST_PORT or 5244
        # 优先使用用户配置的端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", preferred)) != 0:
                return preferred
        # 首选端口被占用，扫描备选端口
        for port in OPENLIST_PORT_RANGE:
            if port == preferred:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        return preferred

    def _generate_config(self, port: int) -> None:
        """生成 OpenList 配置文件"""
        data_dir = self._data_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = data_dir / "config.json"
        db_path = data_dir / "data.db"
        log_path = data_dir / "log.log"

        config = {
            "force": False,
            "site_url": "",
            "cdn": "",
            "login_expiration": 48,
            "database": {
                "type": "sqlite3",
                "host": "",
                "port": 0,
                "user": "",
                "password": "",
                "name": "",
                "db_file": str(db_path).replace("\\", "/"),
                "table_prefix": "x_",
                "ssl_mode": "",
                "dsn": "",
            },
            "scheme": {
                "address": "127.0.0.1",
                "http_port": port,
                "disable_http": False,
                "unix_file": "",
                "unix_file_perm": "",
                "enable_tls": False,
                "cert_file": "",
                "key_file": "",
            },
            "temp_dir": str(data_dir / "temp").replace("\\", "/"),
            "bleve_dir": str(data_dir / "bleve").replace("\\", "/"),
            "dist_dir": "",
            "log": {
                "enable": True,
                "name": str(log_path).replace("\\", "/"),
                "max_size": 10,
                "max_backups": 5,
                "max_age": 28,
                "compress": False,
            },
            "delayed_start": 0,
            "max_connections": 0,
            "tls_insecure_skip_verify": True,
            "tasks": {
                "download": {"workers": 5, "max_retry": 1, "task_persistant": True},
                "transfer": {"workers": 5, "max_retry": 2, "task_persistant": True},
                "upload": {"workers": 5, "max_retry": 1, "task_persistant": False},
                "copy": {"workers": 5, "max_retry": 2, "task_persistant": True},
            },
        }
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"OpenList 配置已生成: {config_file}")

    def _generate_random_password(self, length: int = 16) -> str:
        """生成随机密码"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _login(self, password: str) -> bool:
        """登录 OpenList 获取 Token"""
        if not self._active_port:
            logger.error("无法登录：OpenList 未启动")
            return False
        
        try:
            resp = requests.post(
                f"http://127.0.0.1:{self._active_port}/api/auth/login",
                json={"username": "admin", "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    self._token = data["data"].get("token", "")
                    self._token_expires = time.time() + 3600  # 1小时过期
                    self._logged_in = True
                    logger.info("OpenList 登录成功")
                    return True
                else:
                    logger.error(f"OpenList 登录失败: {data.get('message', '未知错误')}")
                    return False
            else:
                logger.error(f"OpenList 登录请求失败，状态码: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"OpenList 登录异常: {e}")
            return False

    def _auto_login(self) -> dict[str, Any]:
        """自动登录，失败时自动重置密码并重试"""
        if not self._config.OPENLIST_AUTO_LOGIN:
            return {"success": True, "message": "自动登录已禁用"}
        
        password = self._config.OPENLIST_ADMIN_PASSWORD
        if not password:
            return {"success": False, "message": "没有配置管理员密码"}
        
        # 尝试登录
        if self._login(password):
            return {"success": True, "message": "自动登录成功", "logged_in": True}
        
        # 登录失败，尝试重置密码
        if self._config.OPENLIST_AUTO_RESET_PASSWORD:
            logger.warning("登录失败，尝试自动重置密码")
            reset_result = self.reset_admin_password(password)
            if reset_result.get("success"):
                # 重置密码成功后重试登录
                if self._login(password):
                    return {"success": True, "message": "密码重置成功，登录成功", "logged_in": True}
                else:
                    return {"success": False, "message": "密码重置成功，但登录仍失败"}
            else:
                return {"success": False, "message": f"密码重置失败: {reset_result.get('message', '')}"}
        
        return {"success": False, "message": "登录失败，自动重置密码已禁用"}

    def ensure_logged_in(self) -> dict[str, Any]:
        """Ensure OpenList has an admin session for backend management APIs."""
        try:
            self._config.load_config()
        except Exception:
            pass

        self._refresh_external_status()
        if self._status != self.STATUS_RUNNING:
            return {"success": False, "message": "OpenList 未运行", "logged_in": False}
        if self.is_logged_in():
            return {"success": True, "message": "已登录", "logged_in": True}

        password = self._config.OPENLIST_ADMIN_PASSWORD
        if not password:
            return {"success": False, "message": "没有配置管理员密码", "logged_in": False}

        if self._login(password):
            return {"success": True, "message": "登录成功", "logged_in": True}

        if self._config.OPENLIST_AUTO_RESET_PASSWORD:
            logger.warning("OpenList 登录态恢复失败，尝试重置管理员密码")
            reset_result = self.reset_admin_password(password)
            if reset_result.get("success") and self._login(password):
                return {"success": True, "message": "密码重置成功，登录成功", "logged_in": True}
            return {
                "success": False,
                "message": f"登录失败: {reset_result.get('message', '')}",
                "logged_in": False,
            }

        return {"success": False, "message": "登录失败", "logged_in": False}

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        if not self._logged_in:
            return False
        # 检查 Token 是否过期
        if time.time() > self._token_expires - 60:
            self._logged_in = False
            self._token = ""
            return False
        return True

    def get_token(self) -> str:
        """获取当前 Token（如果已登录且未过期）"""
        if self.is_logged_in():
            return self._token
        return ""

    def start(self) -> dict[str, Any]:
        """启动 OpenList 服务器"""
        with self._lock:
            if self._process and self._process.poll() is None:
                return {"success": True, "message": "OpenList 已在运行中", "status": self._status}

            if not self.is_binary_available():
                self._status = self.STATUS_ERROR
                self._error_message = "OpenList 二进制文件不存在，请先下载"
                return {"success": False, "message": self._error_message, "status": self._status}

            # 终止所有旧的 openlist.exe 进程（防止重复启动）
            self._kill_all_openlist_processes()

            self._status = self.STATUS_STARTING
            self._error_message = ""
            
            # 使用配置中的密码，如果没有则生成随机密码
            admin_password = self._config.OPENLIST_ADMIN_PASSWORD
            if not admin_password:
                admin_password = self._generate_random_password()
                self._config.OPENLIST_ADMIN_PASSWORD = admin_password
                self._config.save_config()
            
            available_port = self._find_available_port()

            try:
                self._generate_config(available_port)
                binary = self.get_binary_path()
                data_dir = self._data_dir / "data"

                startupinfo = None
                creation_flags = 0
                if platform.system() == "Windows":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creation_flags = subprocess.CREATE_NO_WINDOW

                # 准备环境变量，包含 admin 密码
                env = os.environ.copy()
                env["OPENLIST_ADMIN_PASSWORD"] = admin_password

                self._process = subprocess.Popen(
                    [str(binary), "server", "--data", str(data_dir)],
                    cwd=str(self._data_dir),
                    startupinfo=startupinfo,
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
                self._start_time = time.time()

                if self._wait_for_ready(available_port):
                    self._status = self.STATUS_RUNNING
                    self._active_port = available_port
                    self._restart_count = 0
                    self._stop_event.clear()
                    self._start_health_thread()
                    logger.info("OpenList started | port: %d | pid: %d", available_port, self._process.pid)

                    login_result = self._auto_login()
                    logged_in = login_result.get("success", False)
                    login_message = login_result.get("message", "")

                    return {
                        "success": True,
                        "message": f"OpenList started{', ' + login_message if login_message else ''}",
                        "status": self._status,
                        "port": available_port,
                        "admin_username": "admin",
                        "admin_password": admin_password,
                        "openlist_username": "admin",
                        "openlist_password": admin_password,
                        "username": "admin",
                        "password": admin_password,
                        "logged_in": logged_in,
                    }
                else:
                    self._status = self.STATUS_ERROR
                    self._error_message = "OpenList 启动超时"
                    self._force_kill()
                    return {"success": False, "message": self._error_message, "status": self._status}

            except Exception as exc:
                self._status = self.STATUS_ERROR
                self._error_message = f"启动失败: {exc}"
                logger.error(f"OpenList 启动失败: {exc}")
                return {"success": False, "message": self._error_message, "status": self._status}

    def stop(self) -> dict[str, Any]:
        """停止 OpenList 服务器"""
        with self._lock:
            if not self._process or self._process.poll() is not None:
                if self._active_port and self._probe_port(self._active_port):
                    self._kill_all_openlist_processes()
                self._status = self.STATUS_STOPPED
                self._process = None
                self._active_port = 0
                self._token = ""
                self._token_expires = 0
                self._logged_in = False
                return {"success": True, "message": "OpenList 已停止", "status": self._status}

            self._stop_event.set()
            pid = self._process.pid
            try:
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=3)
            except Exception as exc:
                logger.warning(f"停止 OpenList 进程异常: {exc}")

            self._process = None
            self._status = self.STATUS_STOPPED
            self._error_message = ""
            self._active_port = 0
            # 清除登录状态
            self._token = ""
            self._token_expires = 0
            self._logged_in = False
            logger.info("OpenList 已停止")
            return {"success": True, "message": "OpenList 已停止", "status": self._status}

    def restart(self) -> dict[str, Any]:
        """重启 OpenList 服务器"""
        self.stop()
        time.sleep(1)
        return self.start()

    def reset_admin_password(self, password: str) -> dict[str, Any]:
        """重置 OpenList admin 密码"""
        binary = self.get_binary_path()
        if not binary.is_file():
            return {"success": False, "message": "OpenList 二进制文件不存在"}

        try:
            data_dir = self._data_dir / "data"
            result = subprocess.run(
                [str(binary), "admin", "set", password, "--data", str(data_dir)],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            if result.returncode == 0:
                self._admin_password = password
                return {"success": True, "message": "密码重置成功"}
            else:
                return {"success": False, "message": f"密码重置失败: {result.stderr or result.stdout}"}
        except Exception as exc:
            return {"success": False, "message": f"密码重置失败: {exc}"}

    def get_status(self) -> dict[str, Any]:
        """获取 OpenList 运行状态"""
        self._refresh_external_status()
        pid = None
        uptime = 0
        if self._process and self._process.poll() is not None:
            pass
        elif self._process:
            pid = self._process.pid
            uptime = int(time.time() - self._start_time)
        elif self._status == self.STATUS_RUNNING and self._start_time:
            uptime = int(time.time() - self._start_time)

        logged_in = self.is_logged_in()
        base_url = f"http://127.0.0.1:{self._active_port or self._config.OPENLIST_PORT or 5244}" if self._status == self.STATUS_RUNNING else ""
        can_mount = bool(self._config.OPENLIST_ENABLED and self._status == self.STATUS_RUNNING and logged_in)

        admin_password = self._config.OPENLIST_ADMIN_PASSWORD or ""
        return {
            "status": self._status,
            "port": self._active_port or self._config.OPENLIST_PORT or 5244,
            "pid": pid,
            "uptime_seconds": uptime,
            "error_message": self._error_message,
            "version": self.get_binary_version(),
            "binary_available": self.is_binary_available(),
            "auto_start": self._config.OPENLIST_AUTO_START,
            "auto_login": self._config.OPENLIST_AUTO_LOGIN,
            "auto_reset_password": self._config.OPENLIST_AUTO_RESET_PASSWORD,
            "enabled": self._config.OPENLIST_ENABLED,
            "base_url": base_url,
            "admin_username": "admin",
            "admin_password": admin_password,
            "openlist_username": "admin",
            "openlist_password": admin_password,
            "username": "admin",
            "password": admin_password,
            "logged_in": logged_in,
            "ready": can_mount,
            "can_mount": can_mount,
            "token_expires_in": max(0, int(self._token_expires - time.time())) if self._token_expires > 0 else 0,
        }

    def _wait_for_ready(self, port: int, timeout: float = 15.0) -> bool:
        """等待服务就绪"""
        url = OPENLIST_CHECK_URL.format(port=port)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(0.5)
        return False

    def _probe_port(self, port: int) -> bool:
        """检查指定端口上是否已有 OpenList 服务。"""
        if not port:
            return False
        try:
            resp = requests.get(OPENLIST_CHECK_URL.format(port=port), timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _refresh_external_status(self) -> None:
        """通过端口探测恢复刷新后丢失的运行态。"""
        try:
            self._config.load_config()
        except Exception:
            pass

        if self._process and self._process.poll() is None:
            return
        if self._process and self._process.poll() is not None:
            self._process = None

        candidate_ports = []
        for port in (self._active_port, self._config.OPENLIST_PORT or 5244, 5244):
            if port and port not in candidate_ports:
                candidate_ports.append(port)

        for port in candidate_ports:
            if self._probe_port(int(port)):
                self._status = self.STATUS_RUNNING
                self._error_message = ""
                self._active_port = int(port)
                if not self._start_time:
                    self._start_time = time.time()
                if self._config.OPENLIST_AUTO_LOGIN and not self.is_logged_in():
                    self._auto_login()
                return

        if not self._process:
            self._status = self.STATUS_STOPPED
            self._active_port = 0
            self._logged_in = False
            self._token = ""
            self._token_expires = 0

    def _start_health_thread(self):
        """启动健康检查线程"""
        if self._health_thread and self._health_thread.is_alive():
            return
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

    def _health_check_loop(self):
        """健康检查循环"""
        fail_count = 0
        while not self._stop_event.is_set():
            self._stop_event.wait(OPENLIST_HEALTH_INTERVAL)
            if self._stop_event.is_set():
                break
            if not self._process or self._process.poll() is not None:
                fail_count += 1
                if fail_count >= OPENLIST_MAX_RESTARTS:
                    logger.error("OpenList 进程异常退出，已达到最大重启次数")
                    with self._lock:
                        self._status = self.STATUS_ERROR
                        self._error_message = "OpenList 进程异常退出"
                        self._process = None
                    break
                logger.warning(f"OpenList 进程异常退出，尝试重启 ({fail_count}/{OPENLIST_MAX_RESTARTS})")
                with self._lock:
                    self._status = self.STATUS_STARTING
                result = self.start(self._active_port)
                if result.get("success"):
                    fail_count = 0
                continue

            port = self._active_port or 5244
            try:
                resp = requests.get(OPENLIST_CHECK_URL.format(port=port), timeout=5)
                if resp.status_code == 200:
                    fail_count = 0
                    continue
            except requests.RequestException:
                pass

            fail_count += 1
            if fail_count >= OPENLIST_MAX_RESTARTS:
                logger.error(f"OpenList 健康检查连续失败 {fail_count} 次，标记为错误状态")
                with self._lock:
                    self._status = self.STATUS_ERROR
                    self._error_message = "OpenList 健康检查失败"
                break

    def _force_kill(self):
        """强制终止进程"""
        if self._process:
            try:
                self._process.kill()
                self._process.wait(timeout=3)
            except Exception:
                pass
            self._process = None


class OpenListBinaryManager:
    """OpenList 二进制下载与版本管理"""

    def __init__(self, data_dir: Optional[Path] = None):
        AppConfig = _get_app_config_class()
        self._config = AppConfig()
        self._config.load_config()
        
        if data_dir is None:
            self._data_dir = self._config.DATA_DIR / "openlist"
        else:
            self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._version_cache: dict[str, Any] = {}

    def get_binary_path(self) -> Path:
        """获取二进制文件路径"""
        ext = ".exe" if platform.system() == "Windows" else ""
        return self._data_dir / f"openlist{ext}"

    def get_platform_info(self) -> tuple[str, str]:
        """获取平台信息"""
        system = platform.system().lower()
        machine = platform.machine().lower()
        os_map = {"windows": "windows", "linux": "linux", "darwin": "darwin"}
        arch_map = {"amd64": "amd64", "x86_64": "amd64", "x64": "amd64", "arm64": "arm64", "aarch64": "arm64"}
        os_name = os_map.get(system, system)
        arch = arch_map.get(machine, "amd64")
        return os_name, arch

    def get_latest_version(self) -> str:
        """获取最新版本号"""
        cache_key = "latest_version"
        cached = self._version_cache.get(cache_key)
        if cached and time.time() - cached["time"] < 3600:
            return cached["version"]

        try:
            resp = requests.get(
                f"https://api.github.com/repos/{OPENLIST_GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=15,
                verify=False,
            )
            resp.raise_for_status()
            data = resp.json()
            version = data.get("tag_name", OPENLIST_FALLBACK_VERSION)
            self._version_cache[cache_key] = {"version": version, "time": time.time()}
            return version
        except Exception as e:
            logger.warning(f"获取最新版本失败，使用默认版本: {e}")
            return OPENLIST_FALLBACK_VERSION

    def check_update(self) -> tuple[bool, Optional[str], str]:
        """检查更新，返回 (是否有更新, 当前版本, 最新版本)"""
        current = self._config.OPENLIST_BINARY_VERSION or ""
        latest = self.get_latest_version()
        if not current:
            return (True, "", latest)
        current_clean = current.lstrip("v")
        latest_clean = latest.lstrip("v")
        return (current_clean != latest_clean, current, latest)

    def download_binary(
        self,
        progress_cb=None,
        version: Optional[str] = None,
    ) -> dict[str, Any]:
        """下载 OpenList 二进制文件"""
        if version is None:
            version = self.get_latest_version()

        os_name, arch = self.get_platform_info()
        
        # 确定文件名
        if os_name == "windows":
            ext = "zip"
            filename = f"OpenList_{os_name}_{arch}.zip"
        else:
            ext = "tar.gz"
            filename = f"OpenList_{os_name}_{arch}.tar.gz"

        # 构建下载 URL
        download_url = f"https://github.com/{OPENLIST_GITHUB_REPO}/releases/download/{version}/{filename}"
        
        # 尝试镜像
        urls_to_try = [download_url]
        for mirror in OPENLIST_MIRRORS:
            mirror_url = f"{mirror}/https://github.com/{OPENLIST_GITHUB_REPO}/releases/download/{version}/{filename}"
            urls_to_try.append(mirror_url)

        archive_path = self._data_dir / f"download.{ext}"
        binary_path = self.get_binary_path()

        for url in urls_to_try:
            try:
                logger.info(f"尝试下载: {url}")
                self._download_file(url, archive_path, progress_cb)
                
                # 解压
                self._extract_binary(archive_path, ext, binary_path)
                
                # 清理
                archive_path.unlink(missing_ok=True)
                
                # 保存版本到配置
                self._config.OPENLIST_BINARY_VERSION = version
                self._config.save_config()
                
                logger.info("OpenList %s 下载完成: %s", version, binary_path)
                return {"success": True, "version": version, "path": str(binary_path)}
            except Exception as e:
                logger.warning(f"下载失败 ({url}): {e}")
                continue

        return {"success": False, "message": "所有下载源均失败，请检查网络"}

    def _download_file(self, url: str, target: Path, progress_cb=None) -> None:
        """下载文件"""
        start_time = time.time()
        with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=True, verify=False) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(target, "wb") as f:
                for chunk in resp.iter_content(chunk_size=OPENLIST_DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    if time.time() - start_time > OPENLIST_DOWNLOAD_TIMEOUT:
                        raise TimeoutError("下载超时")
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(downloaded, total)

    def _extract_binary(self, archive_path: Path, ext: str, target_binary: Path) -> None:
        """从压缩包提取二进制文件"""
        import shutil
        import tarfile
        import zipfile

        if ext == "zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                for name in zf.namelist():
                    basename = name.replace("\\", "/").split("/")[-1]
                    if basename not in {target_binary.name, "openlist.exe", "openlist"}:
                        continue
                    with zf.open(name) as src, open(target_binary, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    return
        else:
            with tarfile.open(archive_path, "r:gz") as tf:
                for member in tf.getmembers():
                    basename = member.name.replace("\\", "/").split("/")[-1]
                    if basename not in {target_binary.name, "openlist"}:
                        continue
                    src = tf.extractfile(member)
                    if src is None:
                        continue
                    with src, open(target_binary, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    return

        raise FileNotFoundError(f"压缩包中未找到 openlist 二进制文件")


# 全局单例
openlist_manager = OpenListManager()
openlist_binary_manager = OpenListBinaryManager()
