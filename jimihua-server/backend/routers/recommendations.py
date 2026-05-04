from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["recommendations"])


class RecommendationRatingPayload(BaseModel):
    movie_path: str
    rating: float = Field(ge=0, le=5)


def _get_services():
    from backend.app import recommendation_service
    return recommendation_service


@router.get("/api/recommendations")
def get_recommendations(
    limit: int = Query(default=18, ge=1, le=48),
    external_limit: int = Query(default=8, ge=0, le=24),
) -> dict[str, Any]:
    return _get_services().get_dashboard(limit=limit, external_limit=external_limit)


@router.post("/api/recommendations/refresh")
def refresh_recommendations() -> dict[str, Any]:
    return _get_services().refresh()


@router.post("/api/recommendations/rate")
def rate_recommendation_movie(payload: RecommendationRatingPayload) -> dict[str, Any]:
    try:
        return _get_services().rate_movie(payload.movie_path, payload.rating)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
