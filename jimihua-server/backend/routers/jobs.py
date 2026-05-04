from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["jobs"])


def _get_job_manager():
    from backend.app import job_manager
    return job_manager


@router.get("/api/jobs/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    job = _get_job_manager().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job.snapshot()
