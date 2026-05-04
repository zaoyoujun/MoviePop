from __future__ import annotations

import os
from typing import Any

from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()


class OpenListService:
    def __init__(self) -> None:
        self.config = AppConfig()

    def get_status(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        return openlist_manager.get_status()

    def get_config(self) -> dict[str, Any]:
        return {
            "enabled": self.config.OPENLIST_ENABLED,
            "port": self.config.OPENLIST_PORT or 5244,
            "admin_password": self.config.OPENLIST_ADMIN_PASSWORD,
            "auto_start": self.config.OPENLIST_AUTO_START,
            "binary_version": self.config.OPENLIST_BINARY_VERSION,
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "enabled" in payload:
            self.config.OPENLIST_ENABLED = bool(payload["enabled"])
        if "port" in payload:
            port = int(payload["port"])
            if 1024 <= port <= 65535:
                self.config.OPENLIST_PORT = port
        if "admin_password" in payload:
            password = str(payload["admin_password"]).strip()
            if password:
                self.config.OPENLIST_ADMIN_PASSWORD = password
        if "auto_start" in payload:
            self.config.OPENLIST_AUTO_START = bool(payload["auto_start"])
        self.config.save_config()
        return self.get_config()

    def start(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        if not openlist_manager.is_binary_available():
            return {"success": False, "message": "OpenList 二进制文件不存在，请先下载"}
        if not self.config.OPENLIST_ADMIN_PASSWORD:
            import secrets
            self.config.OPENLIST_ADMIN_PASSWORD = secrets.token_urlsafe(16)
            self.config.save_config()
        result = openlist_manager.start()
        if result.get("success"):
            self._sync_password_via_api()
        return result

    def _sync_password_via_api(self) -> None:
        from core.openlist_manager import openlist_manager
        from core.openlist_client import OpenListAdminClient
        port = openlist_manager._active_port or self.config.OPENLIST_PORT or 5244
        target_password = self.config.OPENLIST_ADMIN_PASSWORD
        if not target_password:
            return
        client = OpenListAdminClient(f"http://127.0.0.1:{port}")
        try:
            client.login(target_password)
            return
        except Exception:
            pass
        for default_pwd in ("123456", "", "admin"):
            try:
                client.login(default_pwd)
                resp = client.session.post(
                    f"{client.base_url}/api/me/password",
                    headers={"Authorization": client._token},
                    json={"old_password": default_pwd, "new_password": target_password},
                    timeout=10,
                )
                if resp.status_code == 200 and resp.json().get("code") == 200:
                    logger.info("OpenList 密码已通过 API 同步")
                    return
                break
            except Exception:
                continue
        logger.warning("API 密码同步失败，尝试 admin set + 重启")
        import subprocess
        import platform
        binary = openlist_manager.get_binary_path()
        data_dir = openlist_manager._get_openlist_data_dir()
        try:
            subprocess.run(
                [str(binary), "admin", "set", target_password, "--data", str(data_dir)],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            openlist_manager.restart()
        except Exception:
            pass

    def stop(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        return openlist_manager.stop()

    def restart(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        return openlist_manager.restart()

    def reset_password(self, password: str) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        from core.openlist_client import OpenListAdminClient
        port = openlist_manager._active_port or self.config.OPENLIST_PORT or 5244
        client = OpenListAdminClient(f"http://127.0.0.1:{port}")
        old_password = self.config.OPENLIST_ADMIN_PASSWORD or "123456"
        try:
            client.login(old_password)
            resp = client.session.post(
                f"{client.base_url}/api/me/password",
                headers={"Authorization": client._token},
                json={"old_password": old_password, "new_password": password},
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("code") == 200:
                self.config.OPENLIST_ADMIN_PASSWORD = password
                self.config.save_config()
                return {"success": True, "message": "密码重置成功"}
        except Exception:
            pass
        result = openlist_manager.reset_admin_password(password)
        return result

    def download_binary(self) -> str:
        from backend.jobs import job_manager
        from core.openlist_manager import openlist_binary_manager

        def task(update):
            update(0, 100, "正在获取最新版本信息...")
            version = openlist_binary_manager.get_latest_version()
            update(10, 100, f"正在下载 OpenList {version}...")
            openlist_binary_manager.download_binary(
                version,
                progress_cb=lambda cur, total: update(
                    10 + int(cur / total * 80), 100, "正在下载..."
                ) if total > 0 else None,
            )
            update(95, 100, "正在验证文件...")
            self.config.OPENLIST_BINARY_VERSION = version
            self.config.save_config()
            update(100, 100, f"OpenList {version} 下载完成")
            return {"version": version}

        job = job_manager.start("download-openlist-binary", task)
        return job.job_id

    def check_binary_update(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_binary_manager
        has_update, current, latest = openlist_binary_manager.is_update_available()
        return {
            "has_update": has_update,
            "current_version": current,
            "latest_version": latest,
            "binary_available": openlist_binary_manager._openlist_dir.joinpath(
                "openlist.exe" if os.name == "nt" else "openlist"
            ).is_file(),
        }

    def _get_openlist_client(self):
        from core.openlist_manager import openlist_manager
        from core.openlist_client import OpenListAdminClient
        port = openlist_manager._active_port or self.config.OPENLIST_PORT or 5244
        return OpenListAdminClient(f"http://127.0.0.1:{port}")

    def list_storages(self) -> list[dict[str, Any]]:
        client = self._get_openlist_client()
        return client.list_storages(self.config.OPENLIST_ADMIN_PASSWORD)

    def list_directories(self, path: str = "/", recursive: bool = False) -> list[dict[str, str]]:
        client = self._get_openlist_client()
        password = self._ensure_openlist_password(client)
        if recursive:
            return self._list_dirs_recursive(client, password, path)
        return self._list_dirs_at(client, password, path)

    def _ensure_openlist_password(self, client) -> str:
        password = self.config.OPENLIST_ADMIN_PASSWORD or ""
        try:
            client.login(password)
            return password
        except Exception:
            pass
        for default_pwd in ("123456", "", "admin"):
            try:
                client.login(default_pwd)
                if not self.config.OPENLIST_ADMIN_PASSWORD:
                    self.config.OPENLIST_ADMIN_PASSWORD = default_pwd
                    self.config.save_config()
                    logger.info("OpenList 密码已自动同步: %s", default_pwd[:3] + "***")
                return default_pwd
            except Exception:
                continue
        return password

    def _list_dirs_at(self, client, password: str, path: str) -> list[dict[str, str]]:
        try:
            data = client.list_files(password, path)
            content = data.get("data", {}).get("content") or []
            result = [
                {"name": item["name"], "full_path": (path.rstrip("/") + "/" + item["name"]).replace("//", "/")}
                for item in content
                if item.get("is_dir")
            ]
            logger.info("OpenList /api/fs/list path=%s -> %s dirs", path, len(result))
            return result
        except Exception as exc:
            logger.error("OpenList /api/fs/list 失败 path=%s: %s", path, exc)
            raise

    def _list_dirs_recursive(self, client, password: str, root_path: str, max_depth: int = 5) -> list[dict[str, str]]:
        all_dirs: list[dict[str, str]] = []
        queue = [(root_path, 0)]
        visited: set[str] = set()
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            try:
                dirs = self._list_dirs_at(client, password, current)
                for d in dirs:
                    all_dirs.append(d)
                    if depth < max_depth:
                        queue.append((d["full_path"], depth + 1))
            except Exception as exc:
                logger.warning("递归列出目录失败 %s: %s", current, exc)
        return all_dirs

    def add_storage(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.add_storage(self.config.OPENLIST_ADMIN_PASSWORD, payload)

    def update_storage(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.update_storage(self.config.OPENLIST_ADMIN_PASSWORD, payload)

    def delete_storage(self, storage_id: int) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.delete_storage(self.config.OPENLIST_ADMIN_PASSWORD, storage_id)

    def enable_storage(self, storage_id: int) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.enable_storage(self.config.OPENLIST_ADMIN_PASSWORD, storage_id)

    def disable_storage(self, storage_id: int) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.disable_storage(self.config.OPENLIST_ADMIN_PASSWORD, storage_id)

    @staticmethod
    def get_supported_drivers() -> list[dict[str, Any]]:
        from core.openlist_client import OpenListAdminClient
        return OpenListAdminClient.get_supported_drivers()
