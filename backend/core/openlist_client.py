"""
OpenList API client.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional
from urllib.parse import unquote

import requests

# 
logger = logging.getLogger(__name__)

# Supported storage drivers
SUPPORTED_DRIVERS = [
    {
        "driver": "Quark",
        "label": "Quark",
        "fields": [
            {"key": "cookie", "label": "Cookie", "type": "textarea", "required": True},
            {"key": "root_folder_id", "label": "Root Folder ID", "placeholder": "0"},
        ],
    },
    {
        "driver": "AliyundriveOpen",
        "label": "Aliyundrive Open",
        "fields": [
            {"key": "refresh_token", "label": "Refresh Token", "required": True},
            {"key": "root_folder_id", "label": "Root Folder ID", "placeholder": "root"},
            {"key": "drive_type", "label": "Drive Type", "placeholder": "default", "type": "hidden"},
        ],
    },
    {
        "driver": "115 Cloud",
        "label": "115 Cloud",
        "fields": [
            {"key": "cookie", "label": "Cookie", "type": "textarea", "required": True},
            {"key": "root_folder_id", "label": "Root Folder ID", "placeholder": "0"},
        ],
    },
    {
        "driver": "BaiduNetdisk",
        "label": "Baidu Netdisk",
        "fields": [
            {"key": "refresh_token", "label": "Refresh Token", "required": True},
            {"key": "root_folder_path", "label": "Root Folder Path", "placeholder": "/"},
        ],
    },
    {
        "driver": "AList V3",
        "label": "AList V3",
        "fields": [
            {"key": "base_url", "label": "AList URL", "required": True, "placeholder": "http://example.com:5244"},
            {"key": "token", "label": "Token", "required": True},
            {"key": "root_folder_path", "label": "Root Folder Path", "placeholder": "/"},
        ],
    },
    {
        "driver": "WebDav",
        "label": "WebDAV",
        "fields": [
            {"key": "address", "label": "Address", "required": True, "placeholder": "http://example.com/dav"},
            {"key": "username", "label": "Username"},
            {"key": "password", "label": "Password", "type": "password"},
            {"key": "root_folder_path", "label": "Root Folder Path", "placeholder": "/"},
        ],
    },
    {
        "driver": "Local",
        "label": "Local",
        "fields": [
            {"key": "root_folder_path", "label": "Root Folder Path", "required": True, "placeholder": "D:/Videos"},
        ],
    },
    {
        "driver": "SMB",
        "label": "SMB",
        "fields": [
            {"key": "address", "label": "Address", "required": True, "placeholder": "//192.168.1.100/share"},
            {"key": "username", "label": "Username"},
            {"key": "password", "label": "Password", "type": "password"},
            {"key": "root_folder_path", "label": "Root Folder Path", "placeholder": "/"},
        ],
    },
]


class OpenListClient:
    """OpenList API client."""
    def __init__(self, base_url: str = "http://127.0.0.1:5244"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._token: str = ""
        self._token_expires: float = 0

    def set_base_url(self, url: str) -> None:
        """ API """
        self.base_url = url.rstrip("/")

    @staticmethod
    def _api_path(path: str) -> str:
        value = unquote(str(path or "/").strip() or "/")
        if not value.startswith("/"):
            value = "/" + value
        return value

    def is_available(self) -> bool:
        """No description."""
        try:
            resp = self.session.get(f"{self.base_url}/api/public/settings", timeout=3)
            return resp.status_code == 200
        except:
            return False

    def login(self, password: str) -> str:
        """ Token"""
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": "admin", "password": password},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"OpenList : {data.get('message', '')}")
        self._token = data["data"]["token"]
        self._token_expires = time.time() + 3600
        return self._token

    def _ensure_token(self, password: str) -> None:
        """ Token """
        # Refresh token when expired.
        if not self._token or time.time() >= self._token_expires:
            self.login(password)

    def _auth_headers(self, password: str) -> dict[str, str]:
        """No description."""
        self._ensure_token(password)
        # OpenList expects the raw token value.
        return {"Authorization": self._token}

    def _check_response(self, resp: requests.Response) -> dict[str, Any]:
        """No description."""
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"OpenList API : {data.get('message', '')}")
        return data
    
    def _call_api_with_retry(self, method: str, url: str, password: str, **kwargs) -> dict[str, Any]:
        """Call OpenList API with token refresh."""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                if method.lower() == "get":
                    resp = self.session.get(url, headers=self._auth_headers(password), **kwargs)
                elif method.lower() == "post":
                    resp = self.session.post(url, headers=self._auth_headers(password), **kwargs)
                else:
                    raise ValueError(f" HTTP : {method}")
                
                data = resp.json()
                if data.get("code") == 401 or (isinstance(data.get("message"), str) and "token" in data.get("message").lower() and "invalid" in data.get("message").lower()):
                    # Token 
                    logger.warning(f"Token expired, retrying ({attempt + 1})")
                    self._token = ""  # Clear expired token.
                    self.login(password)
                    continue
                
                return self._check_response(resp)
            except RuntimeError as e:
                if "token" in str(e).lower() and "invalid" in str(e).lower():
                    # Token 
                    logger.warning(f"Token refresh failed: {e}, retrying ({attempt + 1})")
                    self._token = ""  # Clear expired token.
                    self.login(password)
                    continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"API call failed: {e}, retrying ({attempt + 1})")
                    time.sleep(1)
                    continue
                raise
        
        raise RuntimeError("OpenList API call failed after retries")

    def list_storages(self, password: str) -> list[dict[str, Any]]:
        """No description."""
        data = self._call_api_with_retry(
            "get",
            f"{self.base_url}/api/admin/storage/list",
            password,
            timeout=10,
        )
        items = data.get("data", {}).get("content", [])
        result = []
        for item in items or []:
            addition = item.get("addition", "{}")
            if isinstance(addition, str):
                try:
                    addition = json.loads(addition)
                except (json.JSONDecodeError, TypeError):
                    addition = {}
            result.append({
                "id": item.get("id"),
                "mount_path": item.get("mount_path", ""),
                "order": item.get("order", 0),
                "driver": item.get("driver", ""),
                "cache_expiration": item.get("cache_expiration", 30),
                "status": item.get("status", "work"),
                "addition": addition,
                "modified": item.get("modified", ""),
            })
        return result

    def add_storage(self, password: str, storage_config: dict[str, Any]) -> dict[str, Any]:
        """"""
        mount_path = storage_config.get("mount_path", "")
        existing_storages = self.list_storages(password)
        for storage in existing_storages:
            if storage.get("mount_path") == mount_path:
                storage_config["id"] = storage.get("id")
                return self.update_storage(password, storage_config)

        addition = storage_config.get("addition", {})
        
        # Quark and 115 use root_folder_id=0 for cloud root.
        if storage_config.get("driver") in {"Quark", "115 Cloud"} and isinstance(addition, dict) and "root_folder_id" not in addition:
            addition["root_folder_id"] = "0"
            logger.info("Set default root_folder_id=0")
        
        if isinstance(addition, dict):
            addition = json.dumps(addition, ensure_ascii=False)
            
        payload = {
            "mount_path": mount_path,
            "order": storage_config.get("order", 0),
            "driver": storage_config.get("driver", ""),
            "cache_expiration": storage_config.get("cache_expiration", 30),
            "status": "work",
            "addition": addition,
        }
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/admin/storage/create",
            password,
            json=payload,
            timeout=15,
        )

    def update_storage(self, password: str, storage_config: dict[str, Any]) -> dict[str, Any]:
        """"""
        addition = storage_config.get("addition", {})
        if isinstance(addition, dict):
            addition = json.dumps(addition, ensure_ascii=False)
        payload = {
            "id": storage_config.get("id"),
            "mount_path": storage_config.get("mount_path", ""),
            "order": storage_config.get("order", 0),
            "driver": storage_config.get("driver", ""),
            "cache_expiration": storage_config.get("cache_expiration", 30),
            "status": storage_config.get("status", "work"),
            "addition": addition,
        }
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/admin/storage/update",
            password,
            json=payload,
            timeout=15,
        )

    def delete_storage(self, password: str, storage_id: int) -> dict[str, Any]:
        """"""
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/admin/storage/delete",
            password,
            params={"id": storage_id},
            timeout=10,
        )

    def enable_storage(self, password: str, storage_id: int) -> dict[str, Any]:
        """"""
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/admin/storage/enable",
            password,
            params={"id": storage_id},
            timeout=10,
        )

    def disable_storage(self, password: str, storage_id: int) -> dict[str, Any]:
        """"""
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/admin/storage/disable",
            password,
            params={"id": storage_id},
            timeout=10,
        )

    def get_me(self, password: str) -> dict[str, Any]:
        """"""
        resp = self.session.get(
            f"{self.base_url}/api/me",
            headers=self._auth_headers(password),
            timeout=10,
        )
        return self._check_response(resp)

    def list_files(
        self,
        password: str,
        path: str = "/",
        page: int = 1,
        per_page: int = 0,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """No description."""
        api_path = self._api_path(path)
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/fs/list",
            password,
            json={"path": api_path, "password": "", "page": page, "per_page": per_page, "refresh": bool(refresh)},
            timeout=15,
        )

    def get_file(self, password: str, path: str, refresh: bool = False) -> dict[str, Any]:
        """"""
        api_path = self._api_path(path)
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/fs/get",
            password,
            json={"path": api_path, "password": "", "refresh": bool(refresh)},
            timeout=10,
        )

    def search(self, password: str, path: str = "/", keyword: str = "", page: int = 1, per_page: int = 50) -> dict[str, Any]:
        """"""
        api_path = self._api_path(path)
        return self._call_api_with_retry(
            "post",
            f"{self.base_url}/api/fs/search",
            password,
            json={"path": api_path, "keyword": keyword, "page": page, "per_page": per_page},
            timeout=30,
        )

    def list_public_files(
        self,
        path: str = "/",
        page: int = 1,
        per_page: int = 50,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """"""
        api_path = self._api_path(path)
        
        # 
        try:
            resp = self.session.get(
                f"{self.base_url}/api/public/list",
                params={"path": api_path, "page": page, "per_page": per_page, "refresh": bool(refresh)},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        
        try:
            resp = self.session.post(
                f"{self.base_url}/api/fs/list",
                json={"path": api_path, "password": "", "page": page, "per_page": per_page, "refresh": bool(refresh)},
                timeout=15,
            )
            return self._check_response(resp)
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_supported_drivers() -> list[dict[str, Any]]:
        """Return supported storage drivers."""
        return SUPPORTED_DRIVERS


openlist_client = OpenListClient()



