from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(tags=["cache"])


def _get_services():
    from backend.app import library_service
    return library_service


@router.post("/api/cache/clear")
def clear_library_cache(source: str = Query(default="")) -> dict[str, bool]:
    _get_services().clear_library_cache(source or None)
    return {"success": True}


@router.post("/api/cache/clear-all")
def clear_all_cache() -> dict[str, bool]:
    _get_services().clear_all_cache()
    return {"success": True}


@router.post("/api/data/clear-all")
def clear_all_data() -> dict[str, bool]:
    _get_services().clear_all_data()
    return {"success": True}
