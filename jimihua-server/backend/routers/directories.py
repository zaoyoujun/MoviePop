from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.logger import get_logger

logger = get_logger()
router = APIRouter(tags=["directories"])


def _get_services():
    from backend.app import config_service
    return config_service


class DirectoryBrowsePayload(BaseModel):
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
    path: str = "/"


@router.get("/api/directories")
def get_webdav_directories(path: str = Query(default="/")) -> list[dict[str, str]]:
    try:
        return _get_services().list_directories(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/directories")
def browse_webdav_directories(payload: DirectoryBrowsePayload) -> list[dict[str, str]]:
    try:
        config_payload = payload.dict()
        path = config_payload.pop("path", "/")
        logger.info("目录浏览请求: path=%s, provider=%s", path, config_payload.get("remote_provider"))
        return _get_services().list_directories(path, config_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/local-directories")
def get_local_directories(path: str = Query(default="")) -> list[dict[str, str]]:
    try:
        return _get_services().list_local_directories(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
