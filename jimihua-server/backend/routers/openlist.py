from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["openlist"])


class OpenListConfigPayload(BaseModel):
    enabled: bool = False
    port: int = 5244
    admin_password: str = ""
    auto_start: bool = True


class OpenListStoragePayload(BaseModel):
    id: int | None = None
    mount_path: str = ""
    driver: str = ""
    addition: dict[str, Any] = Field(default_factory=dict)
    order: int = 0
    cache_expiration: int = 30


def _get_services():
    from backend.app import openlist_service
    return openlist_service


@router.get("/api/openlist/status")
def get_openlist_status() -> dict[str, Any]:
    return _get_services().get_status()


@router.post("/api/openlist/start")
def start_openlist() -> dict[str, Any]:
    return _get_services().start()


@router.post("/api/openlist/stop")
def stop_openlist() -> dict[str, Any]:
    return _get_services().stop()


@router.post("/api/openlist/restart")
def restart_openlist() -> dict[str, Any]:
    return _get_services().restart()


@router.get("/api/openlist/config")
def get_openlist_config() -> dict[str, Any]:
    return _get_services().get_config()


@router.put("/api/openlist/config")
def save_openlist_config(payload: OpenListConfigPayload) -> dict[str, Any]:
    return _get_services().update_config(payload.dict())


@router.post("/api/openlist/download")
def download_openlist_binary() -> dict[str, str]:
    job_id = _get_services().download_binary()
    return {"job_id": job_id}


@router.get("/api/openlist/version")
def check_openlist_version() -> dict[str, Any]:
    return _get_services().check_binary_update()


@router.post("/api/openlist/reset-password")
def reset_openlist_password(payload: dict[str, str]) -> dict[str, Any]:
    password = payload.get("password", "").strip()
    if not password:
        raise HTTPException(status_code=400, detail="密码不能为空")
    return _get_services().reset_password(password)


@router.get("/api/openlist/drivers")
def get_openlist_drivers() -> dict[str, Any]:
    return {"items": _get_services().get_supported_drivers()}


@router.get("/api/openlist/storages")
def list_openlist_storages() -> dict[str, Any]:
    try:
        items = _get_services().list_storages()
        return {"items": items}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/openlist/directories")
def list_openlist_directories(
    path: str = Query(default="/"),
    recursive: bool = Query(default=False),
) -> list[dict[str, str]]:
    try:
        return _get_services().list_directories(path, recursive=recursive)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/openlist/storages")
def add_openlist_storage(payload: OpenListStoragePayload) -> dict[str, Any]:
    try:
        return _get_services().add_storage(payload.dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/openlist/storages")
def update_openlist_storage(payload: OpenListStoragePayload) -> dict[str, Any]:
    try:
        return _get_services().update_storage(payload.dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/openlist/storages")
def delete_openlist_storage(storage_id: int = Query(...)) -> dict[str, Any]:
    try:
        return _get_services().delete_storage(storage_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/openlist/storages/enable")
def enable_openlist_storage(storage_id: int = Query(...)) -> dict[str, Any]:
    try:
        return _get_services().enable_storage(storage_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/openlist/storages/disable")
def disable_openlist_storage(storage_id: int = Query(...)) -> dict[str, Any]:
    try:
        return _get_services().disable_storage(storage_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
