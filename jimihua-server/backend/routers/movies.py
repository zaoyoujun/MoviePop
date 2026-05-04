from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote, urljoin

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from core.remote_source import infer_remote_provider, make_remote_client
from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()
router = APIRouter(tags=["movies"])

_stream_url_cache: dict[str, tuple[str, float]] = {}
_STREAM_URL_TTL = 25 * 60


class MoviePathPayload(BaseModel):
    movie_path: str


class PlayPayload(MoviePathPayload):
    episode_index: int = 0


class UpdateMoviePayload(MoviePathPayload):
    updates: dict[str, Any]


class CandidateSearchPayload(MoviePathPayload):
    custom_name: str | None = None


class CandidateApplyPayload(MoviePathPayload):
    candidate: dict[str, Any]


class RecommendationRatingPayload(MoviePathPayload):
    rating: float = Field(ge=0, le=5)


class PlayerPathPickPayload(BaseModel):
    player: str = "potplayer"
    current_path: str = ""


def _get_services():
    from backend.app import library_service, playback_service, scraper_service, recommendation_service
    return library_service, playback_service, scraper_service, recommendation_service


def _build_stream_client(provider: str | None, movie_path: str):
    config = AppConfig()
    config.load_config()
    resolved_provider = infer_remote_provider(movie_path, default=provider or config.REMOTE_PROVIDER)
    return resolved_provider, make_remote_client(config, resolved_provider)


def _rewrite_m3u8_playlist(playlist_text: str, base_url: str, provider: str) -> str:
    rewritten_lines: list[str] = []
    for raw_line in playlist_text.splitlines():
        line = raw_line.strip()
        if not line:
            rewritten_lines.append(raw_line)
            continue
        if line.startswith("#") and 'URI="' in line:
            start = line.find('URI="')
            if start >= 0:
                prefix = line[: start + 5]
                rest = line[start + 5:]
                end = rest.find('"')
                if end >= 0:
                    uri = rest[:end]
                    absolute = urljoin(base_url, uri)
                    proxied = f"/api/stream/segment?provider={quote(provider)}&upstream={quote(absolute, safe='')}"
                    rewritten_lines.append(f'{prefix}{proxied}"{rest[end + 1:]}')
                    continue
        if line.startswith("#"):
            rewritten_lines.append(raw_line)
            continue
        absolute = urljoin(base_url, line)
        proxied = f"/api/stream/segment?provider={quote(provider)}&upstream={quote(absolute, safe='')}"
        rewritten_lines.append(proxied)
    return "\n".join(rewritten_lines)


def _is_m3u8_content_type(content_type: str) -> bool:
    value = str(content_type or "").lower()
    return "mpegurl" in value or "m3u8" in value or "vnd.apple.mpegurl" in value


def _build_passthrough_headers(response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name in (
        "accept-ranges", "cache-control", "content-disposition",
        "content-length", "content-range", "content-type",
        "etag", "last-modified",
    ):
        value = response.headers.get(name)
        if value:
            headers[name] = value
    return headers


def _build_content_disposition(file_name: str) -> str:
    safe_name = str(file_name or "").strip() or "media.bin"
    encoded_name = quote(safe_name, safe="")
    return f"inline; filename*=UTF-8''{encoded_name}"


def _pick_player_file(player: str, current_path: str = "") -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"当前环境无法打开文件选择器: {exc}") from exc

    player_name = "VLC" if str(player or "").strip().lower() == "vlc" else "PotPlayer"
    initial_path = str(current_path or "").strip()
    initial_dir = ""
    initial_file = ""
    if initial_path:
        if os.path.isdir(initial_path):
            initial_dir = initial_path
        else:
            initial_dir = os.path.dirname(initial_path)
            initial_file = os.path.basename(initial_path)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(
            title=f"选择 {player_name} 可执行文件",
            initialdir=initial_dir or None,
            initialfile=initial_file or None,
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )
        return str(selected or "").strip()
    finally:
        root.destroy()


def _proxy_upstream_response(request, *, upstream_url: str, provider: str, client, file_name: str = ""):
    upstream_headers = {"Accept-Encoding": "identity"}
    for header_name in ("range", "if-range"):
        header_value = request.headers.get(header_name)
        if header_value:
            upstream_headers[header_name] = header_value

    response = client.session.get(
        upstream_url, headers=upstream_headers, timeout=30, stream=True, allow_redirects=True,
    )
    response.raise_for_status()

    media_type = response.headers.get("content-type", "application/octet-stream")
    if _is_m3u8_content_type(media_type):
        playlist_text = response.text
        base_url = response.url.rsplit("/", 1)[0] + "/"
        rewritten = _rewrite_m3u8_playlist(playlist_text, base_url, provider)
        headers = _build_passthrough_headers(response)
        headers.pop("content-length", None)
        response.close()
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl", headers=headers)

    headers = _build_passthrough_headers(response)
    if file_name:
        headers["content-disposition"] = _build_content_disposition(file_name)
    if request.method == "HEAD":
        response.close()
        return Response(status_code=response.status_code, media_type=media_type, headers=headers)

    return StreamingResponse(
        response.iter_content(chunk_size=64 * 1024),
        status_code=response.status_code,
        media_type=media_type,
        headers=headers,
        background=BackgroundTask(response.close),
    )


@router.post("/api/movies/favorite")
def toggle_favorite(payload: MoviePathPayload) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    try:
        movie = library_service.toggle_favorite(payload.movie_path)
        return {"movie": movie, "stats": library_service.get_stats()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/movies/item")
def get_movie_item(movie_path: str = Query(...), source: str | None = Query(default=None)) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    movie = library_service.get_movie(movie_path, source=source)
    if not movie:
        raise HTTPException(status_code=404, detail="未找到对应的影视条目")
    return {"movie": movie}


@router.post("/api/movies/recent")
def add_recent(payload: MoviePathPayload) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    try:
        movie = library_service.add_recent(payload.movie_path)
        return {"movie": movie, "stats": library_service.get_stats()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/movies/recent")
def clear_recent() -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    library_service.cache.clear_recent_play()
    return {"success": True, "stats": library_service.get_stats()}


@router.post("/api/movies/play")
def play_movie(payload: PlayPayload) -> dict[str, Any]:
    _, playback_service, _, _ = _get_services()
    library_service, _, _, _ = _get_services()
    try:
        result = playback_service.play(payload.movie_path, payload.episode_index)
        return {"success": True, "result": result, "stats": library_service.get_stats()}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/movies/update")
def update_movie(payload: UpdateMoviePayload) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    try:
        movie = library_service.save_custom_info(payload.movie_path, payload.updates)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/movies/scrape")
def scrape_single_movie(payload: CandidateSearchPayload) -> dict[str, Any]:
    _, _, scraper_service, _ = _get_services()
    try:
        movie = scraper_service.scrape_single(payload.movie_path, payload.custom_name)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/movies/search-candidates")
def search_movie_candidates(payload: CandidateSearchPayload) -> dict[str, Any]:
    _, _, scraper_service, _ = _get_services()
    try:
        return scraper_service.search_candidates(payload.movie_path, payload.custom_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/movies/apply-candidate")
def apply_movie_candidate(payload: CandidateApplyPayload) -> dict[str, Any]:
    _, _, scraper_service, _ = _get_services()
    try:
        movie = scraper_service.apply_candidate(payload.movie_path, payload.candidate)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/system/pick-player")
def pick_player_file(payload: PlayerPathPickPayload) -> dict[str, str]:
    try:
        return {"path": _pick_player_file(payload.player, payload.current_path)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/movies/{movie_path}/progress")
def save_playback_progress(
    movie_path: str,
    progress: float = Body(..., embed=True),
    duration: float = Body(..., embed=True),
) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    try:
        return library_service.save_playback_progress(movie_path, progress, duration)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/movies/{movie_path}/progress")
def get_playback_progress(movie_path: str) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    try:
        return library_service.get_playback_progress(movie_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/movies/{movie_path}/progress")
def clear_playback_progress(movie_path: str) -> dict[str, Any]:
    library_service, _, _, _ = _get_services()
    try:
        return library_service.clear_playback_progress(movie_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- 流媒体代理 ----

@router.get("/api/stream/playlist.m3u8")
def stream_playlist(
    movie_path: str = Query(...),
    provider: str | None = Query(default=None),
) -> Response:
    try:
        resolved_provider, client = _build_stream_client(provider, movie_path)
        upstream_url = client.get_file_url(movie_path)
        response = client.session.get(upstream_url, timeout=30)
        response.raise_for_status()
        base_url = upstream_url.rsplit("/", 1)[0] + "/"
        rewritten = _rewrite_m3u8_playlist(response.text, base_url, resolved_provider)
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.api_route("/api/stream/media", methods=["GET", "HEAD"])
@router.api_route("/api/stream/media/{media_name}", methods=["GET", "HEAD"])
def stream_media(
    request: Request,
    media_name: str = "",
    movie_path: str = Query(...),
    provider: str | None = Query(default=None),
) -> Response:
    try:
        resolved_provider, client = _build_stream_client(provider, movie_path)
        cache_key = f"{resolved_provider}:{movie_path}"
        now = time.time()
        cached = _stream_url_cache.get(cache_key)
        if cached and now - cached[1] < _STREAM_URL_TTL:
            upstream_url = cached[0]
        else:
            upstream_url = client.get_file_url(movie_path)
            _stream_url_cache[cache_key] = (upstream_url, now)
        return _proxy_upstream_response(
            request, upstream_url=upstream_url, provider=resolved_provider,
            client=client, file_name=media_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.api_route("/api/stream/segment", methods=["GET", "HEAD"])
def stream_segment(
    request: Request,
    upstream: str = Query(...),
    provider: str | None = Query(default=None),
) -> Response:
    try:
        resolved_provider, client = _build_stream_client(provider, "")
        return _proxy_upstream_response(
            request, upstream_url=upstream, provider=resolved_provider, client=client,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
