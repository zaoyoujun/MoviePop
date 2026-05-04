from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["report"])


def _get_services():
    from backend.app import report_service
    return report_service


@router.get("/api/report")
def get_report() -> dict[str, Any]:
    return _get_services().get_report()
