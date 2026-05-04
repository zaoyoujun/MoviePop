from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter(tags=["tags"])


def _get_services():
    from backend.app import library_service
    return library_service


@router.get("/api/tags")
def get_all_tags() -> dict[str, Any]:
    tags = _get_services().get_all_tags()
    return {"tags": tags}


@router.get("/api/movies/{movie_path}/tags")
def get_movie_tags(movie_path: str) -> dict[str, Any]:
    try:
        tags = _get_services().get_movie_tags(movie_path)
        return {"tags": tags}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/movies/{movie_path}/tags")
def add_movie_tag(movie_path: str, tag: str = Body(embed=True)) -> dict[str, Any]:
    try:
        movie = _get_services().add_movie_tag(movie_path, tag)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/movies/{movie_path}/tags/{tag}")
def remove_movie_tag(movie_path: str, tag: str) -> dict[str, Any]:
    try:
        movie = _get_services().remove_movie_tag(movie_path, tag)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/tags/{tag}/movies")
def get_movies_by_tag(tag: str, source: str = Query(default="remote")) -> dict[str, Any]:
    movies = _get_services().get_movies_by_tag(tag, source=source)
    return {"items": movies}
