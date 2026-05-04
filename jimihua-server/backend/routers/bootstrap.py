from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["bootstrap"])


def _get_services():
    from backend.app import config_service, library_service
    return config_service, library_service


@router.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    config_service, library_service = _get_services()
    config = config_service.get_public_config()
    return {
        "config": config,
        "stats": library_service.get_stats(),
        "has_library": config["has_any_library"],
    }
