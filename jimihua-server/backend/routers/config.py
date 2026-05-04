from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["config"])


def _get_services():
    from backend.app import config_service
    return config_service


class ConfigPayload(BaseModel):
    remote_provider: str = "webdav"
    remote_profiles: dict[str, Any] = {}
    webdav_host: str = ""
    webdav_user: str = ""
    webdav_pass: str = ""
    remote_cookie: str = ""
    scan_max_depth: int = 2
    saved_mount_dirs: list[str] = []
    local_scan_max_depth: int = 3
    local_mount_dirs: list[str] = []
    potplayer_path: str = ""
    vlc_path: str = ""
    default_player: str = "potplayer"
    video_formats: list[str] = []
    enable_auto_scrape: bool = True
    scrape_source: str = "auto"
    tmdb_api_key: str = ""
    tmdb_api_base: str = "https://api.themoviedb.org/3"
    tmdb_web_base: str = "https://www.themoviedb.org"
    tmdb_image_base: str = "https://image.tmdb.org/t/p/w500"
    ui_theme: str = "amber"
    interface_theme: str = "amber"
    interface_language: str = "zh"


@router.get("/api/config")
def get_config() -> dict[str, Any]:
    return _get_services().get_public_config()


@router.put("/api/config")
def save_config(payload: ConfigPayload) -> dict[str, Any]:
    return _get_services().update_config(payload.dict())


@router.post("/api/config/test")
def test_config_connection(payload: ConfigPayload | None = None) -> dict[str, Any]:
    success, message = _get_services().test_connection(payload.dict() if payload else None)
    return {"success": success, "message": message}
