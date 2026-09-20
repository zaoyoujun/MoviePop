# -*- coding: utf-8 -*-
"""FastAPI routes for JMH-MoviePop."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlparse

import requests
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

try:
    from backend.api.schemas import api_response
    from backend.services import library_service as lib
    from backend.services import player_service as player
    from backend.services import scan_service
    from backend.services import source_service
    from backend.services import system_service
    from backend.services import analytics_service
    from backend.services import db_service
    from backend.services import recommend_service
    from backend.services import rerank_service
    from backend.core import jobs_state, tmdb_fetcher, scheduler
    from backend.core import llm_client
    from backend.core import llm_scrape
    from backend.services import llm_insight_service
except ImportError:
    from api.schemas import api_response
    from services import library_service as lib
    from services import player_service as player
    from services import scan_service
    from services import source_service
    from services import system_service
    from services import analytics_service
    from services import recommend_service
    from services import rerank_service
    from services import db_service
    from core import jobs_state, tmdb_fetcher, scheduler
    from core import llm_client
    from core import llm_scrape
    from services import llm_insight_service

logger = logging.getLogger(__name__)
router = APIRouter()
_stream_session = requests.Session()
_STREAM_CHUNK_SIZE = 64 * 1024
_STREAM_LOG_INTERVAL = 5.0
_RANGE_PREFETCH_CHUNK_SIZE = 512 * 1024
_RANGE_PREFETCH_WORKERS = 16


def _get_app_config_class():
    try:
        from backend.config import AppConfig
    except ImportError:
        from config import AppConfig
    return AppConfig


def _get_webdav_client_class():
    try:
        from backend.core.webdav_client import WebDAVClient
    except ImportError:
        from core.webdav_client import WebDAVClient
    return WebDAVClient


def _get_openlist_manager():
    try:
        from backend.core.openlist_manager import openlist_manager
    except ImportError:
        from core.openlist_manager import openlist_manager
    return openlist_manager


def _get_openlist_client():
    try:
        from backend.core.openlist_client import SUPPORTED_DRIVERS, openlist_client
    except ImportError:
        from core.openlist_client import SUPPORTED_DRIVERS, openlist_client
    return SUPPORTED_DRIVERS, openlist_client


def _get_cover_scraper_class():
    try:
        from backend.core.cover_scraper import CoverScraper
    except ImportError:
        from core.cover_scraper import CoverScraper
    return CoverScraper


@router.get("/api/health")
async def health_check():
    return api_response(data={"status": "running", "version": "1.0.0"})


@router.get("/api/config")
async def get_config():
    AppConfig = _get_app_config_class()

    config = AppConfig()
    config.load_config()
    return api_response(data=config.get_public_config())


@router.post("/api/config")
async def update_config(request: Request):
    AppConfig = _get_app_config_class()

    try:
        body = await _parse_request_body(request)
        config = AppConfig()
        config.load_config()

        field_map = {
            "openlist_enabled": ("OPENLIST_ENABLED", bool),
            "openlist_port": ("OPENLIST_PORT", int),
            "openlist_auto_start": ("OPENLIST_AUTO_START", bool),
            "openlist_auto_login": ("OPENLIST_AUTO_LOGIN", bool),
            "openlist_auto_reset_password": ("OPENLIST_AUTO_RESET_PASSWORD", bool),
            "scan_max_depth": ("SCAN_MAX_DEPTH", int),
            "local_scan_max_depth": ("LOCAL_SCAN_MAX_DEPTH", int),
            "enable_auto_scrape": ("ENABLE_AUTO_SCRAPE", bool),
        }
        for key, (attr, caster) in field_map.items():
            if key in body:
                setattr(config, attr, _coerce_bool(body[key]) if caster is bool else caster(body[key]))
        config.save_config()
        return api_response(data=config.get_public_config())
    except Exception as exc:
        logger.exception("Update config failed")
        return api_response(code=500, message=str(exc))


@router.get("/api/settings/player")
async def get_player_settings():
    """Return the narrow, non-sensitive preference set for new player windows."""
    AppConfig = _get_app_config_class()
    config = AppConfig()
    config.load_config()
    return api_response(data=config.get_player_settings())


@router.post("/api/settings/player")
async def update_player_settings(request: Request):
    """Persist allowlisted player preferences without accepting arbitrary MPV options."""
    AppConfig = _get_app_config_class()

    try:
        body = await _parse_request_body(request)
        config = AppConfig()
        config.load_config()
        settings = config.update_player_settings(body)
        config.save_config()
        return api_response(data=settings)
    except Exception as exc:
        logger.exception("Update player settings failed")
        return api_response(code=500, message=str(exc))


@router.get("/api/settings/scraper")
async def get_scraper_settings():
    AppConfig = _get_app_config_class()

    config = AppConfig()
    config.load_config()
    return api_response(
        data={
            "enable_auto_scrape": config.ENABLE_AUTO_SCRAPE,
            "scrape_source": config.SCRAPE_SOURCE,
            "scrapeSource": config.SCRAPE_SOURCE,
            "tmdb_api_key": config.TMDB_API_KEY,
            "tmdbApiKey": config.TMDB_API_KEY,
            "tmdb_api_base": config.TMDB_API_BASE,
            "tmdb_image_base": config.TMDB_IMAGE_BASE,
            "douban_cookie": config.DOUBAN_COOKIE,
            "doubanCookie": config.DOUBAN_COOKIE,
        }
    )


@router.post("/api/settings/scraper")
async def update_scraper_settings(request: Request):
    AppConfig = _get_app_config_class()

    try:
        body = await _parse_request_body(request)
        config = AppConfig()
        config.load_config()

        if "enable_auto_scrape" in body:
            config.ENABLE_AUTO_SCRAPE = _coerce_bool(body.get("enable_auto_scrape"))
        if "scrapeSource" in body or "scrape_source" in body:
            config.SCRAPE_SOURCE = str(body.get("scrapeSource", body.get("scrape_source")) or "auto").strip() or "auto"

        if "tmdbApiKey" in body or "tmdb_api_key" in body:
            config.TMDB_API_KEY = str(body.get("tmdbApiKey", body.get("tmdb_api_key")) or "").strip()
        if "tmdb_api_base" in body:
            config.TMDB_API_BASE = str(body.get("tmdb_api_base") or "").strip() or config.TMDB_API_BASE
        if "tmdb_image_base" in body:
            config.TMDB_IMAGE_BASE = str(body.get("tmdb_image_base") or "").strip() or config.TMDB_IMAGE_BASE
        if "doubanCookie" in body or "douban_cookie" in body:
            config.DOUBAN_COOKIE = str(body.get("doubanCookie", body.get("douban_cookie")) or "").strip()

        config.save_config()
        return api_response(
            data={
                "enable_auto_scrape": config.ENABLE_AUTO_SCRAPE,
                "scrape_source": config.SCRAPE_SOURCE,
                "scrapeSource": config.SCRAPE_SOURCE,
                "tmdb_api_key": config.TMDB_API_KEY,
                "tmdbApiKey": config.TMDB_API_KEY,
                "tmdb_api_base": config.TMDB_API_BASE,
                "tmdb_image_base": config.TMDB_IMAGE_BASE,
                "douban_cookie": config.DOUBAN_COOKIE,
                "doubanCookie": config.DOUBAN_COOKIE,
            }
        )
    except Exception as exc:
        logger.exception("Update scraper settings failed")
        return api_response(code=500, message=str(exc))


@router.get("/api/settings/llm")
async def get_llm_settings():
    """返回大模型配置。API Key 不明文回显，仅返回是否已配置与脱敏预览。"""
    AppConfig = _get_app_config_class()
    config = AppConfig()
    config.load_config()
    return api_response(data={
        "llm_enabled": config.LLM_ENABLED,
        "llmEnabled": config.LLM_ENABLED,
        "llm_scrape_enabled": config.LLM_SCRAPE_ENABLED,
        "llmScrapeEnabled": config.LLM_SCRAPE_ENABLED,
        "llm_report_enabled": config.LLM_REPORT_ENABLED,
        "llmReportEnabled": config.LLM_REPORT_ENABLED,
        "llm_rerank_enabled": config.LLM_RERANK_ENABLED,
        "llmRerankEnabled": config.LLM_RERANK_ENABLED,
        "llm_has_key": bool(config.LLM_API_KEY.strip()),
        "llmHasKey": bool(config.LLM_API_KEY.strip()),
        "llm_key_preview": config._mask_secret(config.LLM_API_KEY),
        "llm_base_url": config.LLM_BASE_URL,
        "llmBaseUrl": config.LLM_BASE_URL,
        "llm_model": config.LLM_MODEL,
        "llmModel": config.LLM_MODEL,
        "llm_timeout": config.LLM_TIMEOUT,
    })


@router.post("/api/settings/llm")
async def update_llm_settings(request: Request):
    """保存大模型配置（白名单字段）。llm_api_key 留空表示保持原 Key 不变。"""
    AppConfig = _get_app_config_class()
    try:
        body = await _parse_request_body(request)
        config = AppConfig()
        config.load_config()

        if "llm_enabled" in body:
            config.LLM_ENABLED = _coerce_bool(body.get("llm_enabled"))
        if "llm_scrape_enabled" in body:
            config.LLM_SCRAPE_ENABLED = _coerce_bool(body.get("llm_scrape_enabled"))
        if "llm_report_enabled" in body:
            config.LLM_REPORT_ENABLED = _coerce_bool(body.get("llm_report_enabled"))
        if "llm_rerank_enabled" in body:
            config.LLM_RERANK_ENABLED = _coerce_bool(body.get("llm_rerank_enabled"))
        # 缺省或空串均不改 Key；需要清除时前端显式传 "__clear__"
        raw_key = body.get("llm_api_key", body.get("llmApiKey", None))
        if raw_key is not None:
            if str(raw_key).strip() == "__clear__":
                config.LLM_API_KEY = ""
            elif str(raw_key).strip():
                config.LLM_API_KEY = str(raw_key).strip()
        if "llm_base_url" in body and str(body.get("llm_base_url") or "").strip():
            config.LLM_BASE_URL = str(body.get("llm_base_url")).strip()
        if "llm_model" in body and str(body.get("llm_model") or "").strip():
            config.LLM_MODEL = str(body.get("llm_model")).strip()
        if "llm_timeout" in body:
            config.LLM_TIMEOUT = config._bounded_int(
                body.get("llm_timeout"), config.LLM_TIMEOUT, 5, 60)

        config.save_config()
        return api_response(data={
            "llm_enabled": config.LLM_ENABLED,
            "llmEnabled": config.LLM_ENABLED,
            "llm_scrape_enabled": config.LLM_SCRAPE_ENABLED,
            "llmScrapeEnabled": config.LLM_SCRAPE_ENABLED,
            "llm_report_enabled": config.LLM_REPORT_ENABLED,
            "llmReportEnabled": config.LLM_REPORT_ENABLED,
            "llm_rerank_enabled": config.LLM_RERANK_ENABLED,
            "llmRerankEnabled": config.LLM_RERANK_ENABLED,
            "llm_has_key": bool(config.LLM_API_KEY.strip()),
            "llmHasKey": bool(config.LLM_API_KEY.strip()),
            "llm_key_preview": config._mask_secret(config.LLM_API_KEY),
            "llm_base_url": config.LLM_BASE_URL,
            "llmBaseUrl": config.LLM_BASE_URL,
            "llm_model": config.LLM_MODEL,
            "llmModel": config.LLM_MODEL,
            "llm_timeout": config.LLM_TIMEOUT,
        })
    except Exception as exc:
        logger.exception("Update LLM settings failed")
        return api_response(code=500, message=str(exc))


@router.post("/api/llm/test")
async def test_llm_connection(request: Request):
    """连通性测试：可临时带 body 中的 base_url/model/key（保存前测试），缺省用已保存配置。"""
    try:
        body = await _parse_request_body(request)
    except Exception:
        body = {}

    AppConfig = _get_app_config_class()
    config = AppConfig()
    config.load_config()

    # 保存前测试：body 提供非空值时临时覆盖（不落盘）
    if str(body.get("llm_base_url", body.get("llmBaseUrl", "")) or "").strip():
        config.LLM_BASE_URL = str(body.get("llm_base_url", body.get("llmBaseUrl"))).strip()
    if str(body.get("llm_model", body.get("llmModel", "")) or "").strip():
        config.LLM_MODEL = str(body.get("llm_model", body.get("llmModel"))).strip()
    raw_key = str(body.get("llm_api_key", body.get("llmApiKey", "")) or "").strip()
    if raw_key:
        config.LLM_API_KEY = raw_key

    result = llm_client.test_connection()
    return api_response(data=result, code=0 if result.get("ok") else 1,
                        message=result.get("message") or "")


@router.post("/api/llm/scrape-demo")
async def llm_scrape_demo(request: Request):
    """AI 刮削识别演示：输入一个脏文件名，返回 LLM 识别出的规范片名。

    用于让用户直观验证 G1 是否真的有效，不触发真实刮削。
    body: {"filename": "Show.Name.S02.1080p.x265.mkv"}
    返回: {"original": "...", "needs_llm": bool, "result": {...} | null, "message": str}
    """
    try:
        body = await _parse_request_body(request)
    except Exception:
        body = {}

    filename = str(body.get("filename") or body.get("title") or "").strip()
    if not filename:
        return api_response(code=1, message="请输入文件名", data={"original": "", "needs_llm": False, "result": None})

    needs_llm = llm_scrape.title_needs_llm(filename)
    if not llm_client.feature_enabled("LLM_SCRAPE_ENABLED"):
        return api_response(data={
            "original": filename,
            "needs_llm": needs_llm,
            "result": None,
            "message": "AI 刮削未启用，请先开启「智能刮削识别」并配置 API Key"
        })

    if not needs_llm:
        return api_response(data={
            "original": filename,
            "needs_llm": False,
            "result": None,
            "message": "该文件名已足够干净，规则解析即可，无需 AI 识别"
        })

    # 构造模拟 movie dict，复用 enhance_scrape_title 的完整链路
    movie = {
        "title": filename,
        "files": [{"path": filename}],
        "category": "movie",
        "year_hint": 0,
        "season": 1,
    }
    result = llm_scrape.enhance_scrape_title(movie)
    if not result:
        return api_response(data={
            "original": filename,
            "needs_llm": True,
            "result": None,
            "message": "AI 识别失败或置信度过低，将保留规则标题"
        })

    return api_response(data={
        "original": filename,
        "needs_llm": True,
        "result": result,
        "message": f"AI 识别成功（置信度 {result['confidence']:.0%}）"
    })


@router.post("/api/cache/clear")
async def clear_cache():
    try:
        result = system_service.clear_cache()
        return api_response(code=0 if result.get("ok") else 500, message="ok" if result.get("ok") else "Some cache files could not be deleted", data=result)
    except Exception as exc:
        logger.exception("Clear cache failed")
        return api_response(code=500, message=str(exc), data={"ok": False})


@router.post("/api/cache/clear-all")
async def clear_all_cache():
    return await clear_cache()


@router.post("/api/reset")
async def reset_application():
    try:
        result = system_service.reset_application()
        return api_response(code=0 if result.get("ok") else 500, message="ok" if result.get("ok") else "Application reset completed with errors", data=result)
    except Exception as exc:
        logger.exception("Reset application failed")
        return api_response(code=500, message=str(exc), data={"ok": False})


@router.post("/api/data/clear-all")
async def clear_all_data():
    return await reset_application()


@router.get("/api/sources")
async def list_sources():
    sources = [source_service.safe_source(item) for item in source_service.load_sources()]
    return api_response(data=sources)


@router.post("/api/sources/verify")
async def verify_source(request: Request):
    body = await _parse_request_body(request)
    source_id = str(body.get("source_id") or body.get("sourceId") or "").strip()
    if source_id and not str(body.get("password") or ""):
        # 公开的源列表不返回密码。编辑已有 WebDAV 源时，允许验证接口
        # 在请求未提供新密码的情况下复用其本地保存的密码。
        saved_source = _find_source(source_id)
        if saved_source and source_service.normalize_type(saved_source.get("type") or "") == "webdav":
            body["password"] = saved_source.get("password") or ""
    source_type = source_service.normalize_type(body.get("type") or body.get("provider") or "")
    if source_type in {"web", "remote"}:
        source_type = "webdav"

    if source_type == "local":
        path = str(body.get("path") or body.get("host") or "").strip()
        ok = bool(path and Path(path).exists() and Path(path).is_dir())
        return api_response(
            code=0 if ok else 40001,
            message="ok" if ok else "Local directory does not exist",
            data={"ok": ok},
        )

    if source_type == "webdav":
        host, resolve_error = _resolve_webdav_base_url(body)
        if not host:
            return api_response(code=40001, message=resolve_error or "WebDAV connection failed", data={"ok": False})
        return api_response(data={"ok": True, "base_url": host})

    if source_type == "openlist":
        ok, message, data = _check_openlist_ready()
        return api_response(code=0 if ok else 400, message=message, data={"ok": ok, **data})

    return api_response(code=400, message=f"Unsupported source type: {body.get('type', '')}", data={"ok": False})


@router.post("/api/sources/browse")
async def browse_source_directory(request: Request):
    body = await _parse_request_body(request)
    source_id = str(body.get("source_id") or body.get("sourceId") or "").strip()
    path = str(body.get("path") or "/").strip() or "/"
    if source_id:
        saved_source = _find_source(source_id)
        if not saved_source:
            return api_response(code=404, message="Data source not found", data={"items": []})
        # 保留编辑表单中的主机、端口等改动，但在密码字段为空时复用保存的密码。
        # 这样添加目录不需要再次输入密码，也不会把密码暴露给渲染进程。
        if source_service.normalize_type(body.get("type") or "") == "webdav":
            if not str(body.get("password") or ""):
                body["password"] = saved_source.get("password") or ""
        else:
            return await browse_source_by_id(source_id, path)

    source_type = source_service.normalize_type(body.get("type") or "")
    if source_type == "local":
        return api_response(data={"path": path, "items": _list_local_directory(str(body.get("host") or body.get("path") or ""))})

    if source_type == "openlist":
        if body.get("driver") or body.get("driver_type"):
            return _browse_openlist_preview(body, path)
        return _browse_openlist(path)

    host, resolve_error = _resolve_webdav_base_url(body)
    if not host:
        return api_response(code=40001, message=resolve_error or "WebDAV connection failed", data={"path": path, "items": [], "ok": False})
    WebDAVClient = _get_webdav_client_class()

    try:
        client = WebDAVClient(host=host, username=str(body.get("username") or ""), password=str(body.get("password") or ""))
        items = client.list_directory(path)
        for item in items:
            item["isDir"] = item.get("type") == "folder"
        return api_response(data={"path": path, "items": items, "ok": True, "base_url": host})
    except Exception as exc:
        return api_response(code=40001, message=str(exc), data={"path": path, "items": [], "ok": False, "base_url": host})


@router.get("/api/sources/{source_id}/browse")
async def browse_source_by_id(source_id: str, path: str = Query("/", description="Path to browse")):
    source = _find_source(source_id)
    if not source:
        return api_response(code=404, message="Data source not found", data={"items": []})

    source_type = source.get("type")
    if source_type == "local":
        root = source.get("path", "")
        target = root if path in {"", "/"} else os.path.join(root, path.lstrip("/"))
        return api_response(data={"path": path, "items": _list_local_directory(target)})

    if source_type == "webdav":
        WebDAVClient = _get_webdav_client_class()

        try:
            client = WebDAVClient(host=source.get("path") or _build_webdav_base_url(source), username=source.get("username", ""), password=source.get("password", ""))
            items = client.list_directory(path)
            for item in items:
                item["isDir"] = item.get("type") == "folder"
            return api_response(data={"path": path, "items": items, "ok": True})
        except Exception as exc:
            return api_response(code=40001, message=str(exc), data={"path": path, "items": [], "ok": False})

    if source_type == "openlist":
        return _browse_openlist(path)

    return api_response(code=400, message="Unsupported source type", data={"items": []})


@router.post("/api/sources")
async def add_source(request: Request):
    try:
        body = await _parse_request_body(request)
        source_type = source_service.normalize_type(body.get("type") or body.get("provider") or "")
        if source_type in {"web", "remote"}:
            source_type = "webdav"
        if source_type == "openlist":
            return await add_openlist_source(request)
        if source_type not in {"local", "webdav"}:
            return api_response(code=400, message=f"Unsupported source type: {body.get('type', '')}")

        new_source = _build_source_payload(body, source_type)
        duplicate = _find_duplicate_source(new_source)
        if duplicate:
            return api_response(code=400, message=f"Data source already exists: {duplicate.get('name', '')}")

        sources = source_service.load_sources()
        sources.append(new_source)
        source_service.save_sources(sources)
        scan_status = _maybe_start_scan(new_source, body)
        return api_response(
            message="Data source added successfully, scanning in background",
            data={"source": source_service.safe_source(new_source), "scanStatus": scan_status},
        )
    except Exception as exc:
        logger.exception("Add source failed")
        return api_response(code=500, message=str(exc))


@router.post("/api/sources/{source_id}")
@router.put("/api/sources/{source_id}")
async def update_source(source_id: str, request: Request):
    try:
        body = await _parse_request_body(request)
        sources = source_service.load_sources()
        source = next((item for item in sources if item.get("id") == source_id), None)
        if not source:
            return api_response(code=404, message="Data source not found")

        source_type = source_service.normalize_type(body.get("type") or source.get("type") or "")
        updated = _build_source_payload({**source, **body}, source_type, source_id=source_id, existing=source)
        selected_paths_changed = _normalized_selected_paths(source.get("selected_paths")) != _normalized_selected_paths(updated.get("selected_paths"))

        # mount_path 是 OpenList 的挂载点概念，WebDAV 与本地源不要求它。
        # 之前在所有类型更新时都做严格校验，导致 WebDAV 选择目录后无法保存。
        mount_changed = False
        if source_type == "openlist":
            old_mount_path = _normalize_mount_path(source.get("mount_path") or "")
            new_mount_path = _normalize_mount_path(updated.get("mount_path") or "")
            mount_changed = old_mount_path != new_mount_path

        for index, item in enumerate(sources):
            if item.get("id") == source_id:
                sources[index] = updated
                break
        source_service.save_sources(sources)

        removed_out_of_scope = 0
        if selected_paths_changed:
            removed_out_of_scope = lib.remove_source_movies_outside_paths(
                source_id,
                updated.get("selected_paths") or [],
            )

        if source_type == "openlist" and mount_changed:
            _delete_openlist_storage_for_source(source)
            _create_openlist_storage_for_source(updated)

        scan_status = _maybe_start_scan(updated, body)
        return api_response(data={
            "source": source_service.safe_source(updated),
            "scanStatus": scan_status,
            "removedOutOfScope": removed_out_of_scope,
        })
    except Exception as exc:
        logger.exception("Update source failed")
        return api_response(code=500, message=str(exc))


@router.delete("/api/sources/{source_id}")
async def delete_source(source_id: str):
    source = _find_source(source_id)
    if not source:
        return api_response(code=404, message="Data source not found")

    openlist_cleanup = _delete_openlist_storage_for_source(source) if source.get("type") == "openlist" else {"deleted": False}
    source_service.save_sources([item for item in source_service.load_sources() if item.get("id") != source_id])
    lib.save_library([movie for movie in lib.load_library() if movie.get("source_id") != source_id])
    return api_response(data={"deleted": True, "openlist": openlist_cleanup})


@router.get("/api/sources/{source_id}/scan-status")
async def get_scan_status(source_id: str):
    return api_response(data=scan_service.get_status(source_id))


@router.post("/api/sources/{source_id}/rescan")
async def rescan_source(source_id: str):
    source = _find_source(source_id)
    if not source:
        return api_response(code=404, message="Data source not found")
    status = scan_service.start_background_scan(source_id)
    return api_response(data={"source": source_service.safe_source(source), "scanStatus": status})


@router.post("/api/sources/{source_id}/scan/cancel")
async def cancel_scan_source(source_id: str):
    source = _find_source(source_id)
    if not source:
        return api_response(code=404, message="Data source not found")
    success = scan_service.cancel_scan(source_id)
    return api_response(data={"cancelled": success})


@router.get("/api/openlist/status")
async def get_openlist_status():
    AppConfig = _get_app_config_class()
    openlist_manager = _get_openlist_manager()

    config = AppConfig()
    config.load_config()
    status = openlist_manager.get_status()
    if (
        config.OPENLIST_ENABLED
        and config.OPENLIST_AUTO_LOGIN
        and status.get("status") == "running"
        and not status.get("logged_in")
        and config.OPENLIST_ADMIN_PASSWORD
    ):
        openlist_manager.ensure_logged_in()
        status = openlist_manager.get_status()

    return api_response(data=status)


@router.post("/api/openlist/start")
async def start_openlist():
    AppConfig = _get_app_config_class()
    openlist_manager = _get_openlist_manager()

    config = AppConfig()
    config.load_config()
    if not config.OPENLIST_ENABLED:
        return api_response(code=400, message="Please enable built-in OpenList in settings")
    return api_response(data=openlist_manager.start())


@router.post("/api/openlist/stop")
async def stop_openlist():
    openlist_manager = _get_openlist_manager()

    return api_response(data=openlist_manager.stop())


@router.get("/api/openlist/drivers")
async def get_openlist_drivers():
    return api_response(data=_openlist_drivers_for_api())


@router.get("/api/openlist/storages")
async def list_openlist_storages():
    ok, message, data = _check_openlist_ready()
    if not ok:
        return api_response(code=400, message=message, data=[])
    AppConfig = _get_app_config_class()
    _, openlist_client = _get_openlist_client()

    config = AppConfig()
    config.load_config()
    openlist_client.set_base_url(data["base_url"])
    return api_response(data=openlist_client.list_storages(config.OPENLIST_ADMIN_PASSWORD))


@router.post("/api/openlist/storages/cleanup")
async def cleanup_openlist_storages():
    ok, message, data = _check_openlist_ready()
    if not ok:
        return api_response(code=400, message=message, data={"deleted": []})
    AppConfig = _get_app_config_class()
    _, openlist_client = _get_openlist_client()

    config = AppConfig()
    config.load_config()
    openlist_client.set_base_url(data["base_url"])
    return api_response(data=_cleanup_openlist_orphan_storages(openlist_client, config.OPENLIST_ADMIN_PASSWORD))


@router.post("/api/openlist/browse")
async def browse_openlist_directory(request: Request):
    body = await _parse_request_body(request)
    return _browse_openlist(str(body.get("path") or "/"), int(body.get("page") or 1), int(body.get("per_page") or 100))


@router.post("/api/sources/openlist/mount")
async def add_openlist_source(request: Request):
    try:
        body = await _parse_request_body(request)
        ok, message, ready_data = _check_openlist_ready(require_enabled=True)
        if not ok:
            return api_response(code=400, message=message)

        AppConfig = _get_app_config_class()
        SUPPORTED_DRIVERS, openlist_client = _get_openlist_client()

        config = AppConfig()
        config.load_config()
        password = config.OPENLIST_ADMIN_PASSWORD
        base_url = ready_data["base_url"]
        openlist_client.set_base_url(base_url)

        driver = _label_to_driver(str(body.get("driver") or body.get("driver_type") or body.get("type") or ""))
        valid_drivers = {item.get("driver") for item in SUPPORTED_DRIVERS}
        if driver not in valid_drivers:
            return api_response(code=400, message=f"Unsupported cloud drive type: {body.get('driver') or body.get('type') or ''}")

        mount_path = _normalize_mount_path(body.get("mount_path") or body.get("mountPath") or body.get("path") or _public_openlist_mount_path(driver))
        if _is_preview_mount_path(mount_path) or mount_path.lower() in {"/openlist", "/"}:
            mount_path = _public_openlist_mount_path(driver)
        addition = _apply_openlist_driver_defaults(driver, _coerce_addition(body))
        missing = _missing_openlist_addition(driver, addition)
        if missing:
            return api_response(code=400, message=f"缺少 {missing}")
        storage_config = {
            "driver": driver,
            "mount_path": mount_path,
            "addition": addition,
            "order": int(body.get("order") or 0),
            "cache_expiration": int(body.get("cache_expiration") or 30),
        }
        result = openlist_client.add_storage(password, storage_config)
        if result.get("code") != 200:
            return api_response(code=500, message=result.get("message", "OpenList storage mount failed"))

        storage_data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        raw_selected_paths = _coerce_path_list(body.get("selected_paths") or body.get("selectedPaths"))
        selected_input_paths = [
            _replace_preview_mount(path, _preview_mount_path(driver), mount_path)
            for path in raw_selected_paths
        ]
        selected_paths = _openlist_selected_paths(
            selected_input_paths,
            mount_path,
        )
        new_source = {
            "id": source_service.generate_id(),
            "name": str(body.get("name") or f"OpenList - {mount_path.lstrip('/')}").strip(),
            "type": "openlist",
            "path": base_url,
            "username": "admin",
            "password": "",
            "driver": driver,
            "cookie": addition.get("cookie", ""),
            "addition": addition,
            "storage_id": str(storage_data.get("id", "")),
            "mount_path": mount_path,
            "host": "127.0.0.1",
            "port": str(ready_data.get("port") or ""),
            "protocol": "http",
            "selected_paths": selected_paths or [mount_path],
            "active": True,
            "tint": source_service.random_tint(),
            "stats": _empty_stats(),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

        duplicate = _find_duplicate_source(new_source)
        if duplicate:
            return api_response(code=400, message=f"Data source already exists: {duplicate.get('name', '')}")

        sources = source_service.load_sources()
        sources.append(new_source)
        source_service.save_sources(sources)
        preview_cleanup = _delete_openlist_preview_storage(openlist_client, password, driver)
        scan_status = _maybe_start_scan(new_source, body)
        return api_response(
            message="OpenList data source mounted successfully, scanning in background",
            data={
                "source": source_service.safe_source(new_source),
                "storage": storage_data,
                "previewCleanup": preview_cleanup,
                "scanStatus": scan_status,
            },
        )
    except Exception as exc:
        logger.exception("Mount OpenList source failed")
        return api_response(code=500, message=str(exc))


@router.get("/api/movies/home")
async def get_home_data(category: Optional[str] = None, limit: int = 12):
    return api_response(data=lib.build_home_data(lib.load_library(), category, limit))


@router.get("/api/movies")
async def list_movies(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    source_type: Optional[str] = None,
    favorite: Optional[bool] = None,
    page: int = 1,
    page_size: int = 24,
):
    movies = lib.load_library()
    if category and category != "all":
        target_category = category.lower()
        movies = [
            m for m in movies
            if target_category in lib._api_categories(m)
        ]
    if keyword:
        needle = keyword.lower()
        movies = [m for m in movies if needle in str(m.get("title", "")).lower() or needle in str(m.get("name", "")).lower()]
    if source_type:
        movies = [m for m in movies if m.get("source_type") == source_type]
    if favorite is not None:
        movies = [m for m in movies if bool(m.get("is_favorite")) == favorite]

    total = len(movies)
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 24)))
    start = (page - 1) * page_size
    items = [lib.movie_to_api_format(m) for m in movies[start:start + page_size]]
    return api_response(data={"list": items, "items": items, "pagination": {"page": page, "pageSize": page_size, "total": total}})


@router.get("/api/movies/favorites")
async def get_favorites(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    source_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 24,
):
    return await list_movies(
        category=category,
        keyword=keyword,
        source_type=source_type,
        favorite=True,
        page=page,
        page_size=page_size,
    )


@router.get("/api/movies/history")
async def get_history(page: int = 1, page_size: int = 24):
    movies, total = lib.continue_watching_records(lib.load_library(), page=page, page_size=page_size)
    items = []
    for movie in movies:
        item = lib.history_item_to_api_format(movie)
        item["resumePosition"] = _resume_position(movie)
        items.append(item)
    return api_response(data={"list": items, "pagination": {"page": page, "pageSize": page_size, "total": total}})


@router.get("/api/movies/stats")
async def get_stats(days: int = Query(90, ge=7, le=365)):
    movies = lib.load_library()
    events = db_service.load_behavior_events()
    now = datetime.now()
    viewing_personality = analytics_service.build_personality_profile(days, movies, events, now)
    return api_response(data={
        **lib.compute_stats(movies),
        **lib.compute_home_stats(movies),
        **lib.compute_viewing_insights(movies),
        "periodDays": days,
        "activity": analytics_service.build_activity_summary(days, movies, events, now),
        "personality": viewing_personality,
        "viewingPersonality": viewing_personality,
    })


@router.get("/api/analytics/personality")
async def get_viewing_personality(days: int = Query(90, ge=7, le=365)):
    return api_response(data=analytics_service.build_personality_profile(days))


@router.post("/api/analytics/events")
async def record_analytics_event(request: Request):
    try:
        body = await _parse_request_body(request)
        return api_response(data=analytics_service.record_event(body))
    except ValueError as exc:
        return api_response(code=400, message=str(exc))
    except Exception as exc:
        logger.exception("Record analytics event failed")
        return api_response(code=500, message=str(exc))


@router.post("/api/analytics/event")
async def record_analytics_event_alias(request: Request):
    return await record_analytics_event(request)


@router.post("/api/analytics/llm-report")
async def generate_llm_viewing_report(request: Request):
    """生成 AI 自然语言观影报告（G3）。

    body: {"days": 30, "force_refresh": false, "include_template": false}
    AI 未开启或调用失败时 data.source 为 template，由前端正常展示模板报告。
    include_template=true 且 AI 成功时，data.templateReport 附带模板版供对比。
    """
    try:
        body = await _parse_request_body(request)
        days = int(body.get("days", 30) or 30)
        force_refresh = _coerce_bool(body.get("force_refresh", False))
        include_template = _coerce_bool(body.get("include_template", False))
        data = llm_insight_service.generate_viewing_report(
            days, force_refresh=force_refresh, include_template=include_template
        )
        return api_response(data=data, message=data.get("message") or "ok")
    except Exception as exc:
        logger.exception("Generate LLM viewing report failed")
        return api_response(code=500, message=str(exc))


@router.get("/api/scrape/sources")
async def get_scrape_sources():
    return api_response(data=[
        {"label": "Auto", "value": "auto"},
        {"label": "TMDB", "value": "tmdb"},
        {"label": "AniBK", "value": "anibk"},
        {"label": "Douban", "value": "douban"},
    ])


@router.post("/api/scrape/search")
async def manual_scrape_search(request: Request):
    body = await _parse_request_body(request)
    keyword = str(body.get("keyword") or body.get("title") or "").strip()
    source = str(body.get("source") or "auto").strip().lower()
    if not keyword:
        return api_response(code=400, message="Missing keyword")
    try:
        return api_response(data=_manual_scrape_search(keyword, source))
    except Exception as exc:
        logger.exception("Manual scrape search failed")
        return api_response(code=500, message=f"Manual scrape search failed: {exc}")


@router.post("/api/scrape/submit")
async def manual_scrape_submit(request: Request):
    body = await _parse_request_body(request)
    movie_id = str(body.get("movie_id") or body.get("movieId") or "").strip()
    metadata = body.get("data") or {}
    if not movie_id:
        return api_response(code=400, message="Missing movie_id")
    if not isinstance(metadata, dict):
        return api_response(code=400, message="Invalid metadata")

    movies = lib.load_library()
    target = None
    for movie in movies:
        if movie.get("id") == movie_id:
            target = movie
            break
    if not target:
        return api_response(code=404, message="Movie not found")

    try:
        submit_source = str(metadata.get("source") or body.get("source") or "manual")
        apply_mode = str(body.get("applyMode") or body.get("apply_mode") or metadata.get("applyMode") or metadata.get("apply_mode") or "all")
        clear_empty = _coerce_bool(body.get("clearEmpty", body.get("clear_empty", False)))
        lock_metadata = body.get("metadataLocked", body.get("metadata_locked", metadata.get("metadataLocked", metadata.get("metadata_locked"))))
        _apply_manual_scrape_metadata(
            target,
            metadata,
            submit_source,
            apply_mode=apply_mode,
            clear_empty=clear_empty,
            lock_metadata=None if lock_metadata is None else _coerce_bool(lock_metadata),
        )
        lib.save_library(movies)
        return api_response(data=lib.movie_to_detail(target))
    except Exception as exc:
        logger.exception("Manual scrape submit failed")
        return api_response(code=500, message=f"Manual scrape submit failed: {exc}")


@router.post("/api/movies/{movie_id}/metadata/custom")
async def update_custom_metadata(movie_id: str, request: Request):
    body = await _parse_request_body(request)
    metadata = body.get("data") if isinstance(body.get("data"), dict) else body
    movies = lib.load_library()
    target = next((movie for movie in movies if movie.get("id") == movie_id), None)
    if not target:
        return api_response(code=404, message="Movie not found")
    try:
        _apply_manual_scrape_metadata(
            target,
            metadata,
            "manual",
            apply_mode=str(body.get("applyMode") or body.get("apply_mode") or "all"),
            clear_empty=_coerce_bool(body.get("clearEmpty", body.get("clear_empty", False))),
            lock_metadata=_coerce_bool(body.get("metadataLocked", body.get("metadata_locked", True))),
        )
        lib.save_library(movies)
        return api_response(data=lib.movie_to_detail(target))
    except Exception as exc:
        logger.exception("Update custom metadata failed")
        return api_response(code=500, message=f"Update custom metadata failed: {exc}")


@router.post("/api/movies/{movie_id}/metadata/lock")
async def set_metadata_lock(movie_id: str, request: Request):
    body = await _parse_request_body(request)
    locked = _coerce_bool(body.get("locked", body.get("metadataLocked", body.get("metadata_locked", True))))
    movies = lib.load_library()
    target = next((movie for movie in movies if movie.get("id") == movie_id), None)
    if not target:
        return api_response(code=404, message="Movie not found")
    target["metadata_locked"] = locked
    target["updated_at"] = _now_iso()
    lib.save_library(movies)
    return api_response(data=lib.movie_to_detail(target))


@router.get("/api/movies/{movie_id}")
async def get_movie_detail(movie_id: str):
    movie = lib.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    try:
        analytics_service.record_event({"event_type": "detail_view", "movie_id": movie_id})
    except Exception as exc:
        logger.debug("Record detail view failed: movie=%s error=%s", movie_id, exc)
    return api_response(data=lib.movie_to_detail(movie))


@router.get("/api/movies/{movie_id}/recommendations")
async def get_movie_recommendations(movie_id: str, limit: int = 12):
    movie = lib.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    recommendations = lib.get_recommendations(movie_id, limit)
    return api_response(data=recommendations)


@router.post("/api/movies/{movie_id}/favorite")
async def add_favorite(movie_id: str):
    return _set_favorite(movie_id, True)


@router.delete("/api/movies/{movie_id}/favorite")
async def remove_favorite(movie_id: str):
    return _set_favorite(movie_id, False)


@router.post("/api/movies/{movie_id}/home-presentation")
async def set_home_presentation(movie_id: str):
    movie = lib.set_home_presentation(movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    return api_response(data=lib.movie_to_api_format(movie))


@router.post("/api/movies/{movie_id}/playback")
async def update_movie_playback(movie_id: str, request: Request):
    body = await _parse_request_body(request)
    episode_id = str(body.get("episode_id") or body.get("episodeId") or "").strip()
    effective_movie_id = _effective_movie_id(movie_id, episode_id)
    episode_number = int(body.get("episode_number") or body.get("episodeNumber") or _episode_number_from_id(episode_id) or 0)
    current_time = int(float(body.get("current_time") or body.get("currentTime") or 0))
    duration = int(float(body.get("duration") or 0))
    watch_seconds_delta = int(float(
        body.get("watch_seconds_delta")
        or body.get("watchSecondsDelta")
        or body.get("played_seconds")
        or body.get("playedSeconds")
        or 0
    ))
    movie = lib.get_movie_by_id(effective_movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    if not episode_id and episode_number <= 0:
        episode_id = _resolve_resume_episode_id(movie, "")
        effective_movie_id = _effective_movie_id(movie_id, episode_id)
        movie = lib.get_movie_by_id(effective_movie_id) or movie
        episode_number = _episode_number_from_id(episode_id)
    if episode_number <= 0:
        playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
        try:
            episode_number = int(playback.get("current_episode") or 0)
        except (TypeError, ValueError):
            episode_number = 0
    lib.update_playback(effective_movie_id, episode_number, current_time, duration, watch_seconds_delta, episode_id)
    try:
        analytics_service.record_play_heartbeat(
            effective_movie_id,
            episode_id,
            position=current_time,
            duration=duration,
            delta_seconds=watch_seconds_delta,
            playback_rate=float(body.get("playback_rate") or body.get("playbackRate") or 1),
        )
    except Exception as exc:
        logger.debug("Record playback heartbeat failed: movie=%s error=%s", effective_movie_id, exc)
    updated_movie = lib.get_movie_by_id(effective_movie_id) or {}
    playback = updated_movie.get("playback") if isinstance(updated_movie.get("playback"), dict) else {}
    episode_playback = _playback_for_episode(updated_movie, episode_id)
    return api_response(data={
        "id": effective_movie_id,
        "episodeId": episode_id,
        "episodeNumber": episode_number,
        "currentTime": current_time,
        "duration": duration,
        "percent": playback.get("percent", 0),
        "watchSeconds": playback.get("watch_seconds", 0),
        "episodeProgress": {
            "currentTime": episode_playback.get("current_time", 0),
            "duration": episode_playback.get("duration", 0),
            "percent": episode_playback.get("percent", 0),
            "watchSeconds": episode_playback.get("watch_seconds", 0),
            "lastPlayTime": episode_playback.get("last_play_time", ""),
        },
    })


@router.get("/api/movies/{movie_id}/play")
async def get_play_info(movie_id: str, episode_id: Optional[str] = None, player_type: str = "web"):
    movie = lib.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    try:
        episode_id = _resolve_resume_episode_id(movie, episode_id)
        effective_movie_id = _effective_movie_id(movie_id, episode_id)
        effective_movie = lib.get_movie_by_id(effective_movie_id) or movie
        source_type = effective_movie.get("source_type")
        if source_type in {"openlist", "webdav"}:
            play_url = _movie_stream_url(effective_movie_id, episode_id)
            headers = {"x-moviepop-prefetch": "parallel"} if source_type == "openlist" else {}
        else:
            play_url, headers = lib.resolve_play_url(movie, episode_id, source_service.load_sources())
        resume_position = _resume_position(effective_movie, episode_id)
        return api_response(data={
            "id": effective_movie_id,
            "episodeId": episode_id,
            "playUrl": play_url,
            "headers": headers,
            "sourceType": effective_movie.get("source_type", ""),
            "playerType": player_type,
            "resumePosition": resume_position,
        })
    except Exception as exc:
        return api_response(code=500, message=f"Failed to get playback URL: {exc}")


@router.post("/api/player/play")
async def player_play(movie_id: str = Query(...), episode_id: Optional[str] = None, position: int = 0):
    movie = lib.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    episode_id = _resolve_resume_episode_id(movie, episode_id)
    effective_movie_id = _effective_movie_id(movie_id, episode_id)
    effective_movie = lib.get_movie_by_id(effective_movie_id) or movie
    if int(position or 0) <= 0:
        position = _resume_position(effective_movie, episode_id)
    source_type = effective_movie.get("source_type")
    sources = source_service.load_sources()
    if source_type == "openlist":
        ok, message = _preflight_openlist_stream(movie, episode_id, sources)
        if not ok:
            return api_response(code=403, message=message, data={"running": False, "movieId": effective_movie_id, "episodeId": episode_id or ""})
        play_url = _movie_stream_url(effective_movie_id, episode_id)
        headers = {"x-moviepop-prefetch": "parallel"}
    elif source_type == "webdav":
        play_url = _movie_stream_url(effective_movie_id, episode_id)
        headers = {}
    else:
        play_url, headers = lib.resolve_play_url(movie, episode_id, sources)
    ok = player.get_player().play(
        play_url,
        position=position,
        title=effective_movie.get("title", ""),
        headers=headers,
        context={
            "movie_id": effective_movie_id,
            "episode_id": episode_id or "",
            "root_movie_id": movie_id,
            "api_base": _api_base_url(),
        },
    )
    if ok:
        _record_playback_start(effective_movie_id, episode_id)
    return api_response(
        code=0 if ok else 500,
        message="ok" if ok else "Player start failed",
        data={"running": ok, "resumePosition": position, "movieId": effective_movie_id, "episodeId": episode_id or ""},
    )


@router.get("/api/movies/{movie_id}/stream")
def stream_movie(movie_id: str, request: Request, episode_id: Optional[str] = None):
    movie = lib.get_movie_by_id(movie_id)
    if not movie:
        return JSONResponse(status_code=404, content={"code": 404, "message": "Movie not found", "data": None})

    episode_id = _resolve_resume_episode_id(movie, episode_id)
    sources = source_service.load_sources()
    try:
        play_url, headers = lib.resolve_play_url(movie, episode_id, sources)
    except Exception as exc:
        logger.exception("Video proxy resolve failed: movie=%s episode=%s", movie_id, episode_id or "")
        return JSONResponse(status_code=500, content={"code": 500, "message": f"Failed to resolve video stream: {exc}", "data": None})
    upstream_headers = dict(headers or {})
    upstream_headers.setdefault("Connection", "keep-alive")
    range_header = request.headers.get("range")
    if range_header:
        upstream_headers["Range"] = range_header

    started_at = time.monotonic()
    logger.info("Video proxy request: movie=%s episode=%s range=%s", movie_id, episode_id or "", range_header or "-")
    try:
        upstream = _stream_session.get(play_url, headers=upstream_headers, stream=True, timeout=(10, 60))
    except Exception as exc:
        logger.exception("Video proxy upstream request failed: movie=%s episode=%s", movie_id, episode_id or "")
        return JSONResponse(status_code=502, content={"code": 502, "message": f"Upstream video stream request failed: {exc}", "data": None})
    if upstream.status_code not in (200, 206):
        body = upstream.text[:500]
        upstream.close()
        if (
            movie.get("source_type") == "openlist"
            and upstream.status_code in (401, 403)
            and _is_expired_openlist_stream_error(body)
        ):
            logger.warning("OpenList stream URL expired, refreshing and retrying once: movie=%s episode=%s", movie_id, episode_id or "")
            try:
                play_url, headers = lib.resolve_play_url(movie, episode_id, sources, refresh=True)
                upstream_headers = dict(headers or {})
                upstream_headers.setdefault("Connection", "keep-alive")
                if range_header:
                    upstream_headers["Range"] = range_header
                upstream = _stream_session.get(play_url, headers=upstream_headers, stream=True, timeout=(10, 60))
                if upstream.status_code in (200, 206):
                    logger.info("OpenList stream URL refresh succeeded: movie=%s episode=%s", movie_id, episode_id or "")
                else:
                    body = upstream.text[:500]
                    upstream.close()
            except Exception as exc:
                logger.exception("OpenList stream URL refresh failed: movie=%s episode=%s", movie_id, episode_id or "")
                return JSONResponse(status_code=502, content={"code": 502, "message": f"OpenList stream refresh failed: {exc}", "data": None})
        if upstream.status_code in (200, 206):
            pass
        else:
            message = _expired_openlist_message() if _is_expired_openlist_stream_error(body) else f"Upstream video stream request failed: {body}"
            return JSONResponse(
                status_code=upstream.status_code,
                content={"code": upstream.status_code, "message": message, "data": None},
            )
    if upstream.status_code not in (200, 206):
        message = _expired_openlist_message() if _is_expired_openlist_stream_error(body) else f"Upstream video stream request failed: {body}"
        return JSONResponse(
            status_code=upstream.status_code,
            content={"code": upstream.status_code, "message": message, "data": None},
        )
    logger.info(
        "Video proxy upstream response: status=%s first_byte=%.2fs content_length=%s content_range=%s",
        upstream.status_code,
        time.monotonic() - started_at,
        upstream.headers.get("Content-Length", "-"),
        upstream.headers.get("Content-Range", "-"),
    )

    response_headers = {
        "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
        "Content-Disposition": "inline",
        "Access-Control-Expose-Headers": "Content-Range, Content-Length, Content-Type",
    }
    for key in ("Content-Type", "Content-Length", "Content-Range"):
        value = upstream.headers.get(key)
        if value:
            response_headers[key] = value

    open_range_start = _parse_open_ended_range(range_header)
    content_range = _parse_content_range(upstream.headers.get("Content-Range", ""))
    if open_range_start is not None and content_range and request.headers.get("x-moviepop-prefetch", "").lower() == "parallel":
        range_start, _range_end, total_size = content_range
        upstream.close()
        response_headers["Content-Length"] = str(total_size - range_start)
        response_headers["Content-Range"] = f"bytes {range_start}-{total_size - 1}/{total_size}"
        logger.info(
            "Video proxy enabled parallel range fetching: start=%s total=%s chunk=%s workers=%s",
            range_start,
            total_size,
            _RANGE_PREFETCH_CHUNK_SIZE,
            _RANGE_PREFETCH_WORKERS,
        )
        return StreamingResponse(
            _parallel_range_iterator(play_url, upstream_headers, range_start, total_size - 1, started_at),
            status_code=206,
            headers=response_headers,
        )

    def iterator():
        sent = 0
        last_log_at = time.monotonic()
        try:
            for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK_SIZE):
                if chunk:
                    sent += len(chunk)
                    now = time.monotonic()
                    if now - last_log_at >= _STREAM_LOG_INTERVAL:
                        elapsed = max(0.001, now - started_at)
                        speed_mbps = sent * 8 / elapsed / 1024 / 1024
                        logger.info("Video proxy transferring: sent=%.1fMiB avg=%.2fMbps", sent / 1024 / 1024, speed_mbps)
                        last_log_at = now
                    yield chunk
        finally:
            elapsed = max(0.001, time.monotonic() - started_at)
            logger.info("Video proxy finished: sent=%.1fMiB avg=%.2fMbps", sent / 1024 / 1024, sent * 8 / elapsed / 1024 / 1024)
            upstream.close()

    return StreamingResponse(iterator(), status_code=upstream.status_code, headers=response_headers)


def _parse_open_ended_range(range_header: str | None) -> int | None:
    if not range_header:
        return None
    match = re.fullmatch(r"bytes=(\d+)-", range_header.strip())
    if not match:
        return None
    return int(match.group(1))


def _is_expired_openlist_stream_error(body: str) -> bool:
    text = str(body or "").lower()
    return any(
        marker in text
        for marker in (
            "auth expired",
            "require login",
            "user not login",
            "login expired",
            "requestdeniedbycallback",
        )
    )


def _expired_openlist_message() -> str:
    return "OpenList/Quark 登录已过期，后端已阻止启动播放器以避免黑屏。请在 OpenList 或数据源里更新夸克 Cookie 后重试播放。"


def _preflight_openlist_stream(movie: dict, episode_id: Optional[str], sources: list[dict[str, Any]]) -> tuple[bool, str]:
    for refresh in (False, True):
        try:
            play_url, headers = lib.resolve_play_url(movie, episode_id, sources, refresh=refresh)
            response = _stream_session.get(
                play_url,
                headers={**(headers or {}), "Range": "bytes=0-0"},
                stream=True,
                timeout=(8, 15),
            )
            try:
                if response.status_code in (200, 206):
                    return True, "ok"
                body = response.text[:500]
                if response.status_code in (401, 403) and _is_expired_openlist_stream_error(body):
                    if not refresh:
                        continue
                    return False, _expired_openlist_message()
                return False, f"OpenList upstream rejected playback: HTTP {response.status_code}"
            finally:
                response.close()
        except Exception as exc:
            if refresh:
                return False, f"OpenList playback preflight failed: {exc}"
    return False, _expired_openlist_message()


def _parse_content_range(content_range: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", str(content_range or "").strip())
    if not match or match.group(3) == "*":
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _download_range_chunk(play_url: str, headers: dict[str, str], start: int, end: int) -> bytes:
    request_headers = dict(headers or {})
    request_headers["Range"] = f"bytes={start}-{end}"
    last_error: Exception | None = None
    for _attempt in range(3):
        response = None
        try:
            response = requests.get(play_url, headers=request_headers, timeout=(10, 45))
            if response.status_code != 206:
                raise RuntimeError(f"Range {start}-{end} returned status {response.status_code}")
            return response.content
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
        finally:
            if response is not None:
                response.close()
    raise RuntimeError(f"Download range failed {start}-{end}: {last_error}")


def _parallel_range_iterator(play_url: str, headers: dict[str, str], start: int, end: int, started_at: float):
    sent = 0
    last_log_at = time.monotonic()
    expected_start = start
    next_start = start
    pending = {}

    def submit_more(executor: ThreadPoolExecutor):
        nonlocal next_start
        while len(pending) < _RANGE_PREFETCH_WORKERS and next_start <= end:
            chunk_end = min(end, next_start + _RANGE_PREFETCH_CHUNK_SIZE - 1)
            pending[next_start] = executor.submit(_download_range_chunk, play_url, headers, next_start, chunk_end)
            next_start = chunk_end + 1

    with ThreadPoolExecutor(max_workers=_RANGE_PREFETCH_WORKERS) as executor:
        try:
            submit_more(executor)
            while expected_start <= end:
                future = pending.pop(expected_start)
                data = future.result()
                chunk_len = len(data)
                if chunk_len <= 0:
                    raise RuntimeError(f"绌哄垎鐗? {expected_start}")

                submit_more(executor)
                for offset in range(0, chunk_len, _STREAM_CHUNK_SIZE):
                    piece = data[offset:offset + _STREAM_CHUNK_SIZE]
                    sent += len(piece)
                    now = time.monotonic()
                    if now - last_log_at >= _STREAM_LOG_INTERVAL:
                        elapsed = max(0.001, now - started_at)
                        speed_mbps = sent * 8 / elapsed / 1024 / 1024
                        logger.info(
                            "Video proxy parallel transferring: sent=%.1fMiB avg=%.2fMbps pending=%s",
                            sent / 1024 / 1024,
                            speed_mbps,
                            len(pending),
                        )
                        last_log_at = now
                    yield piece
                expected_start += chunk_len
        finally:
            for future in pending.values():
                future.cancel()
            elapsed = max(0.001, time.monotonic() - started_at)
            logger.info("Video proxy parallel finished: sent=%.1fMiB avg=%.2fMbps", sent / 1024 / 1024, sent * 8 / elapsed / 1024 / 1024)


@router.post("/api/player/stop")
async def player_stop():
    return api_response(data={"stopped": player.get_player().stop()})


@router.post("/api/player/pause")
@router.post("/api/player/resume")
async def player_noop():
    return api_response(data={"ok": True})


@router.post("/api/player/next")
async def player_next():
    return _play_adjacent_episode(1)


@router.post("/api/player/previous")
async def player_previous():
    return _play_adjacent_episode(-1)


@router.post("/api/player/seek")
@router.post("/api/player/seek_relative")
@router.post("/api/player/volume")
@router.post("/api/player/mute")
async def player_control_noop():
    return api_response(data={"ok": True})


@router.get("/api/player/status")
async def player_status():
    return api_response(data={"running": player.get_player().is_running()})


def _get_online_extractor():
    try:
        from backend.core.online_extractor import browse_site, extract_video_detail, generate_online_movie_entry
    except ImportError:
        from core.online_extractor import browse_site, extract_video_detail, generate_online_movie_entry
    return browse_site, extract_video_detail, generate_online_movie_entry


@router.post("/api/online/browse")
async def online_browse(request: Request):
    body = await _parse_request_body(request)
    url = str(body.get("url") or "").strip()
    if not url:
        return api_response(code=400, message="Missing URL")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browse_site, _, _ = _get_online_extractor()
    result = browse_site(url)
    if result.get("error"):
        return api_response(code=400, message=result["error"], data=result)
    return api_response(data=result)


@router.post("/api/online/detail")
async def online_detail(request: Request):
    body = await _parse_request_body(request)
    url = str(body.get("url") or "").strip()
    if not url:
        return api_response(code=400, message="Missing URL")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    _, extract_video_detail, _ = _get_online_extractor()
    result = extract_video_detail(url)
    if result.get("error"):
        return api_response(code=400, message=result["error"], data=result)
    return api_response(data=result)


@router.post("/api/online/add")
async def online_add(request: Request):
    body = await _parse_request_body(request)
    video_info = body.get("video")
    if not isinstance(video_info, dict):
        return api_response(code=400, message="Invalid video info")
    
    _, _, generate_online_movie_entry = _get_online_extractor()
    movie_entry = generate_online_movie_entry(video_info)
    
    movies = lib.load_library()
    existing = next((m for m in movies if m.get("id") == movie_entry["id"]), None)
    if existing:
        return api_response(code=400, message="Video already added")
    
    movies.append(movie_entry)
    lib.save_library(movies)
    return api_response(data=lib.movie_to_api_format(movie_entry))


@router.delete("/api/online/{video_id}")
async def online_remove(video_id: str):
    movies = lib.load_library()
    before = len(movies)
    movies = [m for m in movies if m.get("source_type") != "online" or m.get("id") != video_id]
    if len(movies) == before:
        return api_response(code=404, message="Video not found")
    lib.save_library(movies)
    return api_response(data={"deleted": True})


async def _parse_request_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            return body if isinstance(body, dict) else {}
        except Exception:
            return {}
    try:
        form = await request.form()
        return {key: value for key, value in form.items()}
    except Exception:
        return {}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _effective_movie_id(movie_id: str, episode_id: Optional[str] = None) -> str:
    value = str(episode_id or "")
    if "::" in value:
        embedded_movie_id, _episode_key = value.split("::", 1)
        embedded_movie_id = embedded_movie_id.strip()
        if embedded_movie_id:
            return embedded_movie_id
    return movie_id


def _episode_number_from_id(episode_id: Optional[str] = None) -> int:
    value = str(episode_id or "")
    match = re.search(r"ep(\d+)", value, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"E(\d{1,3})\b", value, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def _resolve_resume_episode_id(movie: dict, episode_id: Optional[str] = None) -> str:
    explicit_episode_id = str(episode_id or "").strip()
    if explicit_episode_id:
        return explicit_episode_id

    playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
    current_episode_id = str(playback.get("current_episode_id") or "").strip()
    if current_episode_id and current_episode_id != "default":
        return current_episode_id
    try:
        current_episode = int(playback.get("current_episode") or 0)
    except (TypeError, ValueError):
        current_episode = 0
    if current_episode <= 0:
        return ""

    try:
        detail = lib.movie_to_detail(movie)
        movie_id = str(movie.get("id") or "")
        for season in detail.get("seasons") or []:
            for episode in season.get("episodes") or []:
                episode_number = int(episode.get("episodeNumber") or episode.get("episode_number") or 0)
                episode_movie_id = str(episode.get("movieId") or season.get("movieId") or season.get("id") or "")
                if episode_number == current_episode and (not episode_movie_id or episode_movie_id == movie_id):
                    return str(episode.get("episodeId") or episode.get("id") or "").strip()
        for season in detail.get("seasons") or []:
            for episode in season.get("episodes") or []:
                episode_number = int(episode.get("episodeNumber") or episode.get("episode_number") or 0)
                if episode_number == current_episode:
                    return str(episode.get("episodeId") or episode.get("id") or "").strip()
    except Exception as exc:
        logger.debug("Resolve resume episode failed: movie=%s error=%s", movie.get("id", ""), exc)
    return ""


def _playback_for_episode(movie: dict, episode_id: Optional[str] = None) -> dict:
    playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
    explicit_episode_id = str(episode_id or "").strip()
    if explicit_episode_id:
        episodes = playback.get("episodes") if isinstance(playback.get("episodes"), dict) else {}
        entry = episodes.get(explicit_episode_id)
        if isinstance(entry, dict):
            return entry
        episode_number = _episode_number_from_id(explicit_episode_id)
        if episode_number:
            entry = episodes.get(f"ep{episode_number}")
            if isinstance(entry, dict):
                return entry
    return playback


def _resume_position(movie: dict, episode_id: Optional[str] = None) -> int:
    playback = _playback_for_episode(movie, episode_id)
    try:
        current_time = int(float(playback.get("current_time") or 0))
        duration = int(float(playback.get("duration") or 0))
        percent = float(playback.get("percent") or 0)
    except (TypeError, ValueError):
        return 0
    if current_time < 8:
        return 0
    if percent >= 90:
        return 0
    if duration > 0 and duration - current_time < 30:
        return 0
    return max(0, current_time - 3)


def _play_adjacent_episode(direction: int):
    instance = player.get_player()
    context = getattr(instance, "current_context", {}) or {}
    current_movie_id = str(context.get("movie_id") or context.get("root_movie_id") or "").strip()
    current_episode_id = str(context.get("episode_id") or "").strip()
    if not current_movie_id:
        return api_response(code=400, message="No active playback context")

    current_movie = lib.get_movie_by_id(current_movie_id)
    if not current_movie:
        return api_response(code=404, message="Current movie not found")

    target = _find_adjacent_episode(current_movie, current_episode_id, direction)
    if not target:
        return api_response(code=404, message="No adjacent episode")

    target_movie_id = target["movie_id"]
    target_episode_id = target["episode_id"]
    target_movie = lib.get_movie_by_id(target_movie_id)
    if not target_movie:
        return api_response(code=404, message="Target movie not found")

    source_type = target_movie.get("source_type")
    if source_type in {"openlist", "webdav"}:
        play_url = _movie_stream_url(target_movie_id, target_episode_id)
        headers = {"x-moviepop-prefetch": "parallel"} if source_type == "openlist" else {}
    else:
        play_url, headers = lib.resolve_play_url(target_movie, target_episode_id, source_service.load_sources())
    target_context = {
        "movie_id": target_movie_id,
        "episode_id": target_episode_id,
        "root_movie_id": target_movie_id,
        "api_base": _api_base_url(),
    }
    ok = instance.switch_source(
        play_url,
        position=0,
        title=target_movie.get("title", ""),
        headers=headers,
        context=target_context,
    )
    if not ok:
        ok = instance.play(
            play_url,
            position=0,
            title=target_movie.get("title", ""),
            headers=headers,
            context=target_context,
            allow_rapid=True,
        )
    if ok:
        _record_playback_start(target_movie_id, target_episode_id)
    return api_response(
        code=0 if ok else 500,
        message="ok" if ok else "Player start failed",
        data={"running": ok, "movieId": target_movie_id, "episodeId": target_episode_id, "episodeNumber": target.get("episode_number", 0)},
    )


def _find_adjacent_episode(movie: dict, episode_id: str, direction: int) -> Optional[dict[str, Any]]:
    detail = lib.movie_to_detail(movie)
    entries: list[dict[str, Any]] = []
    for season_index, season in enumerate(detail.get("seasons") or []):
        for episode in season.get("episodes") or []:
            entries.append({
                "movie_id": str(episode.get("movieId") or season.get("movieId") or season.get("id") or movie.get("id")),
                "episode_id": str(episode.get("episodeId") or episode.get("id") or ""),
                "episode_number": int(episode.get("episodeNumber") or 0),
                "season_index": season_index,
            })
    if not entries:
        return None
    if not episode_id:
        current_number = 0
        playback = movie.get("playback") if isinstance(movie.get("playback"), dict) else {}
        try:
            current_number = int(playback.get("current_episode") or 0)
        except (TypeError, ValueError):
            current_number = 0
        if current_number:
            episode_id = next((item["episode_id"] for item in entries if item["movie_id"] == movie.get("id") and item["episode_number"] == current_number), "")
    current_index = next((index for index, item in enumerate(entries) if item["episode_id"] == episode_id), None)
    if current_index is None:
        current_index = next((index for index, item in enumerate(entries) if item["movie_id"] == movie.get("id")), 0)
    target_index = current_index + (1 if direction >= 0 else -1)
    if target_index < 0 or target_index >= len(entries):
        return None
    return entries[target_index]


def _record_playback_start(movie_id: str, episode_id: Optional[str] = None) -> None:
    if not movie_id:
        return
    try:
        movie = lib.get_movie_by_id(movie_id) or {}
        playback = _playback_for_episode(movie, episode_id)
        episode_number = _episode_number_from_id(episode_id) or int(playback.get("current_episode") or 0)
        current_time = int(float(playback.get("current_time") or 0))
        duration = int(float(playback.get("duration") or 0))
        lib.update_playback(movie_id, episode_number, current_time, duration, episode_id=episode_id or "")
        analytics_service.record_play_start(movie_id, episode_id or "", position=current_time, duration=duration)
    except Exception as exc:
        logger.debug("Failed to record playback start: movie=%s error=%s", movie_id, exc)


def _movie_stream_url(movie_id: str, episode_id: Optional[str] = None) -> str:
    path = f"/api/movies/{quote(str(movie_id), safe='')}/stream"
    query = urlencode({"episode_id": episode_id}) if episode_id else ""
    return f"{_api_base_url()}{path}" + (f"?{query}" if query else "")


def _api_base_url() -> str:
    AppConfig = _get_app_config_class()
    config = AppConfig()
    config.load_config()
    return f"http://127.0.0.1:{config.SERVER_PORT}"


def _empty_stats() -> dict[str, int]:
    return {"files": 0, "movies": 0, "series": 0, "anime": 0, "music": 0, "unmatched": 0}


def _manual_scrape_search(keyword: str, source: str) -> list[dict[str, Any]]:
    source = (source or "auto").lower()
    if source == "auto":
        results: list[dict[str, Any]] = []
        provider_errors: list[str] = []
        for item in ("anibk", "tmdb", "douban"):
            try:
                results.extend(_manual_scrape_search(keyword, item))
            except Exception as exc:
                # One provider being unavailable must not hide results from the
                # remaining providers (for example, an expired TMDB key).
                logger.warning("Manual scrape provider unavailable: source=%s error=%s", item, exc)
                provider_errors.append(f"{item}: {exc}")
        if not results and len(provider_errors) == 3:
            raise RuntimeError(f"All scrape providers failed: {'; '.join(provider_errors)}")
        return _dedupe_manual_scrape_results(results)
    if source == "anibk":
        return _manual_search_anibk(keyword)
    if source == "tmdb":
        return _manual_search_tmdb(keyword)
    if source == "douban":
        return _manual_search_douban(keyword)
    return []


def _manual_search_anibk(keyword: str) -> list[dict[str, Any]]:
    scraper = _get_cover_scraper_class()()
    results = []
    for candidate in scraper._search_anibk(keyword)[:10]:
        detail_url = candidate.get("url", "")
        cover_url = scraper._get_anibk_cover(detail_url) if detail_url else ""
        description = scraper._get_anibk_intro(detail_url) if detail_url else ""
        release_info = scraper._get_anibk_release_info(detail_url) if detail_url else {}
        year = release_info.get("year", 0)
        results.append({
            "title": candidate.get("title", ""),
            "source": "anibk",
            "sourceId": detail_url,
            "url": detail_url,
            "year": year,
            "releaseDate": release_info.get("release_date", ""),
            "genres": ["anime"],
            "country": "JP",
            "score": 0,
            "description": description,
            "posterUrl": cover_url,
            "coverUrl": cover_url,
        })
    return results


def _manual_search_tmdb(keyword: str) -> list[dict[str, Any]]:
    AppConfig = _get_app_config_class()
    config = AppConfig()
    config.load_config()
    api_key = str(getattr(config, "TMDB_API_KEY", "") or "").strip()
    if not api_key:
        return []

    base = str(getattr(config, "TMDB_API_BASE", "") or "https://api.themoviedb.org/3").rstrip("/")
    response = requests.get(
        f"{base}/search/multi",
        params={"api_key": api_key, "query": keyword, "language": "zh-CN", "include_adult": "false"},
        timeout=12,
    )
    response.raise_for_status()
    scraper = _get_cover_scraper_class()()
    items = []
    for item in response.json().get("results", []) or []:
        media_type = item.get("media_type")
        if media_type not in {"movie", "tv"}:
            continue
        title = item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name") or ""
        raw_release_date = item.get("release_date") or item.get("first_air_date") or ""
        year = _extract_year_from_text(raw_release_date)
        poster = scraper._tmdb_image_url(item.get("poster_path") or "", "poster")
        backdrop = scraper._tmdb_image_url(item.get("backdrop_path") or "", "backdrop")
        items.append({
            "title": title,
            "source": "tmdb",
            "sourceId": item.get("id"),
            "tmdbId": item.get("id"),
            "tmdbMediaType": media_type,
            "year": year,
            "releaseDate": scraper._normalize_release_date(raw_release_date),
            "genres": [],
            "country": "",
            "score": round(float(item.get("vote_average") or 0), 1),
            "voteCount": int(item.get("vote_count") or 0),
            "description": item.get("overview") or "",
            "posterUrl": poster,
            "coverUrl": poster,
            "backdropUrl": backdrop,
            "originalTitle": item.get("original_title") or item.get("original_name") or "",
        })
    return items[:10]


def _manual_search_douban(keyword: str) -> list[dict[str, Any]]:
    scraper = _get_cover_scraper_class()()
    candidates = scraper._search_douban_candidates(keyword)[:8]
    if not candidates:
        result = scraper._scrape_douban(keyword)
        return [_manual_douban_payload(result, keyword)] if result.get("title") or result.get("cover_url") else []

    results = []
    for candidate in candidates:
        detail_url = str(candidate.get("url") or "").strip()
        if not detail_url:
            continue
        try:
            detail = scraper._scrape_douban_detail(
                detail_url,
                str(candidate.get("title") or keyword),
                int(candidate.get("year") or 0),
                1,
                float(candidate.get("match_score") or 0),
            )
        except Exception as exc:
            logger.debug("Manual douban detail enrich failed: url=%s error=%s", detail_url, exc)
            detail = {}
        if not detail.get("douban_url"):
            detail["douban_url"] = detail_url
        if not detail.get("title"):
            detail["title"] = candidate.get("title") or keyword
        if not detail.get("year"):
            detail["year"] = candidate.get("year") or 0
        payload = _manual_douban_payload(detail, keyword)
        if payload.get("title") or payload.get("coverUrl"):
            results.append(payload)
    return results


def _manual_douban_payload(result: dict[str, Any], keyword: str) -> dict[str, Any]:
    cover_url = result.get("cover_url", "")
    return {
        "title": result.get("title") or keyword,
        "source": "douban",
        "sourceId": result.get("douban_url", ""),
        "url": result.get("douban_url", ""),
        "year": result.get("year", 0),
        "releaseDate": result.get("release_date", ""),
        "genres": result.get("genres") or result.get("tags") or [],
        "country": " / ".join(result.get("countries") or []),
        "score": result.get("score", 0),
        "description": result.get("description", ""),
        "duration": result.get("duration", ""),
        "posterUrl": cover_url,
        "coverUrl": cover_url,
        "backdropUrl": result.get("backdrop_url") or cover_url,
        "voteCount": result.get("vote_count", 0),
        "originalTitle": result.get("original_title", ""),
    }


def _dedupe_manual_scrape_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in results:
        key = (str(item.get("source") or ""), str(item.get("sourceId") or item.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:20]


def _metadata_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return list(dict.fromkeys([str(item).strip() for item in value if str(item).strip()]))
    if isinstance(value, str):
        return list(dict.fromkeys([item.strip() for item in re.split(r"[,/|，、]", value) if item.strip()]))
    return []


def _metadata_text(metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in metadata:
            return str(metadata.get(key) or "").strip()
    return ""


def _apply_manual_scrape_metadata(
    movie: dict[str, Any],
    metadata: dict[str, Any],
    source: str,
    apply_mode: str = "all",
    clear_empty: bool = False,
    lock_metadata: bool | None = None,
) -> None:
    scraper = _get_cover_scraper_class()()
    mode = str(apply_mode or "all").strip().lower()
    if mode not in {"all", "metadata", "poster", "cover", "backdrop"}:
        mode = "all"
    apply_text = mode in {"all", "metadata"}
    apply_poster = mode in {"all", "poster", "cover"}
    apply_backdrop = mode in {"all", "backdrop"}

    title = _metadata_text(metadata, "title", "name")
    if apply_text and title:
        movie["metadata_title"] = title
        movie["display_title"] = title
    elif apply_text and clear_empty and ("title" in metadata or "name" in metadata):
        movie["metadata_title"] = ""
        movie["display_title"] = movie.get("title", "")

    description = _metadata_text(metadata, "description", "overview", "intro")
    if apply_text and description:
        movie["intro"] = description
    elif apply_text and clear_empty and any(key in metadata for key in ("description", "overview", "intro")):
        movie["intro"] = ""

    if apply_text and ("year" in metadata):
        try:
            year = int(metadata.get("year") or 0)
            if year or clear_empty:
                movie["year"] = year or None
        except (TypeError, ValueError):
            if clear_empty:
                movie["year"] = None

    if apply_text and ("releaseDate" in metadata or "release_date" in metadata):
        release_date = scraper._normalize_release_date(_metadata_text(metadata, "releaseDate", "release_date"))
        if release_date or clear_empty:
            movie["release_date"] = release_date
            movie["release_date_checked"] = True

    if apply_text and ("score" in metadata or "rating" in metadata):
        score = metadata.get("score") if "score" in metadata else metadata.get("rating")
        try:
            movie["rating"] = float(score or 0)
            movie["rating_checked"] = True
        except (TypeError, ValueError):
            if clear_empty:
                movie["rating"] = 0
                movie["rating_checked"] = True

    cover_url = str(metadata.get("coverUrl") or metadata.get("posterUrl") or metadata.get("poster") or "").strip()
    backdrop_url = str(metadata.get("backdropUrl") or metadata.get("backdrop") or "").strip()
    season = int(movie.get("season") or 1)
    if apply_poster and cover_url:
        movie["cover_url"] = _download_manual_image(scraper, cover_url, movie.get("title") or title, season, "poster") or cover_url
    elif apply_poster and clear_empty and any(key in metadata for key in ("coverUrl", "posterUrl", "poster")):
        movie["cover_url"] = ""
    if apply_backdrop and backdrop_url:
        movie["backdrop_url"] = _download_manual_image(scraper, backdrop_url, movie.get("title") or title, season, "backdrop") or backdrop_url
    elif apply_backdrop and clear_empty and any(key in metadata for key in ("backdropUrl", "backdrop")):
        movie["backdrop_url"] = ""
    elif mode == "all" and movie.get("cover_url") and not movie.get("backdrop_url"):
        movie["backdrop_url"] = movie.get("cover_url")

    if apply_text:
        genres = _metadata_list(metadata.get("genres") if "genres" in metadata else metadata.get("tags"))
        if genres or (clear_empty and ("genres" in metadata or "tags" in metadata)):
            movie["genres"] = genres
        tags = _metadata_list(metadata.get("tags"))
        if tags:
            movie["tags"] = list(dict.fromkeys([*tags, *movie.get("genres", [])]))
        elif genres:
            current_tags = movie.get("tags") if isinstance(movie.get("tags"), list) else []
            movie["tags"] = list(dict.fromkeys([*current_tags, *genres]))
        elif clear_empty and "tags" in metadata:
            movie["tags"] = []

        countries = _metadata_list(metadata.get("countries"))
        if not countries:
            countries = _metadata_list(metadata.get("country"))
        if countries or (clear_empty and ("countries" in metadata or "country" in metadata)):
            movie["countries"] = countries

        languages = _metadata_list(metadata.get("languages"))
        if languages or (clear_empty and "languages" in metadata):
            movie["languages"] = languages

        duration = _metadata_text(metadata, "duration", "durationText")
        if duration or (clear_empty and ("duration" in metadata or "durationText" in metadata)):
            movie["duration"] = duration

        movie["original_title"] = metadata.get("originalTitle") or metadata.get("original_title") or ("" if clear_empty and ("originalTitle" in metadata or "original_title" in metadata) else movie.get("original_title", ""))
        movie["tmdb_id"] = metadata.get("tmdbId") or metadata.get("tmdb_id") or ("" if clear_empty and ("tmdbId" in metadata or "tmdb_id" in metadata) else movie.get("tmdb_id", ""))
        movie["tmdb_media_type"] = metadata.get("tmdbMediaType") or metadata.get("tmdb_media_type") or ("" if clear_empty and ("tmdbMediaType" in metadata or "tmdb_media_type" in metadata) else movie.get("tmdb_media_type", ""))
        movie["douban_url"] = metadata.get("url") if source == "douban" else metadata.get("doubanUrl") or metadata.get("douban_url") or movie.get("douban_url", "")
        movie["vote_count"] = metadata.get("voteCount") or metadata.get("vote_count") or movie.get("vote_count", 0)

    movie["metadata_source"] = source or str(metadata.get("source") or "manual")
    if lock_metadata is not None:
        movie["metadata_locked"] = bool(lock_metadata)
    movie["updated_at"] = _now_iso()


def _download_manual_image(scraper, image_url: str, title: str, season: int, image_type: str = "poster") -> str:
    if not image_url.startswith(("http://", "https://")):
        return image_url
    try:
        return scraper._download_cover(image_url, title, season, image_type=image_type)
    except Exception as exc:
        logger.debug("Manual image download failed: %s", exc)
        return ""


def _extract_year_from_text(text: str) -> int:
    match = re.search(r"(19\d{2}|20\d{2}|21\d{2})", str(text or ""))
    return int(match.group(1)) if match else 0


def _build_source_payload(body: dict[str, Any], source_type: str, source_id: str | None = None, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _now_iso()
    selected_paths_input = body["selected_paths"] if "selected_paths" in body else body.get("selectedPaths")
    selected_paths = _coerce_path_list(selected_paths_input)
    selected_paths_provided = "selected_paths" in body or "selectedPaths" in body
    name = str(body.get("name") or (existing or {}).get("name") or f"Source {now}").strip()
    driver = ""
    mount_path = ""

    if source_type == "local":
        path = str(body.get("path") or body.get("host") or "").strip()
        if not path:
            raise ValueError("Missing local directory path")
        host = ""
        protocol = ""
        port = ""
    elif source_type == "openlist":
        host = str(body.get("host") or (existing or {}).get("host") or "127.0.0.1").strip()
        protocol = str(body.get("protocol") or (existing or {}).get("protocol") or "http").strip()
        port = str(body.get("port") or (existing or {}).get("port") or "").strip()
        path = str(body.get("path") or (existing or {}).get("path") or "").strip()
        if not path:
            path = f"{protocol or 'http'}://{host}" + (f":{port}" if port else "")
        driver = _label_to_driver(str(body.get("driver") or body.get("driver_type") or (existing or {}).get("driver") or ""))
        mount_path = _normalize_openlist_source_mount(body, existing, selected_paths, driver)
        selected_paths = _openlist_selected_paths(selected_paths, mount_path)
    else:
        path, _resolve_error = _resolve_webdav_base_url(body)
        if not path:
            path = _build_webdav_base_url(body)
        if not path:
            raise ValueError("Missing WebDAV address")
        host = str(body.get("host") or "").strip()
        protocol = str(body.get("protocol") or "http").strip()
        port = str(body.get("port") or "").strip()

    password = str(body.get("password") or "")
    if existing and not password:
        password = existing.get("password", "")

    return {
        "id": source_id or source_service.generate_id(),
        "name": name,
        "type": source_type,
        "path": path,
        "username": str(body.get("username") or ""),
        "password": password,
        "driver": driver if source_type == "openlist" else str(body.get("driver") or ""),
        "cookie": str(body.get("cookie") or (existing or {}).get("cookie") or ""),
        "addition": body.get("addition") if isinstance(body.get("addition"), dict) else (existing or {}).get("addition", {}),
        "storage_id": str(body.get("storage_id") or (existing or {}).get("storage_id") or ""),
        "mount_path": mount_path if source_type == "openlist" else str(body.get("mount_path") or body.get("mountPath") or ""),
        "host": host,
        "port": port,
        "protocol": protocol or "http",
        "selected_paths": selected_paths if selected_paths_provided else ([path] if source_type == "local" else ["/"]),
        "active": _coerce_bool(body.get("active", True)),
        "tint": (existing or {}).get("tint") or source_service.random_tint(),
        "stats": (existing or {}).get("stats") or _empty_stats(),
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
        "scan_error": "",
    }


def _find_source(source_id: str) -> dict[str, Any] | None:
    return next((item for item in source_service.load_sources() if item.get("id") == source_id), None)


def _find_duplicate_source(candidate: dict[str, Any]) -> dict[str, Any] | None:
    for item in source_service.load_sources():
        if item.get("id") == candidate.get("id"):
            continue
        if item.get("type") != candidate.get("type"):
            continue
        if candidate.get("type") == "openlist":
            if (
                item.get("mount_path") == candidate.get("mount_path")
                and item.get("selected_paths") == candidate.get("selected_paths")
            ):
                return item
            continue
        if item.get("path") == candidate.get("path") and item.get("selected_paths") == candidate.get("selected_paths"):
            return item
    return None


def _delete_openlist_storage_for_source(source: dict[str, Any]) -> dict[str, Any]:
    ok, message, ready_data = _check_openlist_ready()
    if not ok:
        return {"deleted": False, "skipped": True, "message": message}

    AppConfig = _get_app_config_class()
    _, openlist_client = _get_openlist_client()
    config = AppConfig()
    config.load_config()
    openlist_client.set_base_url(ready_data["base_url"])

    driver = _label_to_driver(str(source.get("driver") or ""))
    mount_path = _normalize_mount_path(source.get("mount_path") or _public_openlist_mount_path(driver))
    if _is_preview_mount_path(mount_path) or mount_path.lower() in {"/", "/openlist"}:
        mount_path = _public_openlist_mount_path(driver)

    deleted: list[str] = []
    errors: list[str] = []
    storage_id = str(source.get("storage_id") or "").strip()

    try:
        storages = openlist_client.list_storages(config.OPENLIST_ADMIN_PASSWORD)
    except Exception as exc:
        logger.warning("List OpenList storages failed before delete: %s", exc)
        return {"deleted": False, "message": str(exc)}

    target_ids: list[int] = []
    target_mounts: set[str] = set()
    for storage in storages:
        sid = storage.get("id")
        storage_mount = _normalize_mount_path(storage.get("mount_path") or "/")
        storage_driver = _label_to_driver(str(storage.get("driver") or ""))
        is_same_id = storage_id and str(sid) == storage_id
        is_same_mount = storage_mount == mount_path
        is_preview_for_driver = bool(driver and storage_driver == driver and storage_mount == _preview_mount_path(driver))
        if sid is not None and (is_same_id or is_same_mount or is_preview_for_driver):
            target_mounts.add(storage_mount)
            try:
                target_ids.append(int(sid))
            except (TypeError, ValueError):
                errors.append(f"Invalid storage id for {storage_mount}: {sid}")

    if not target_ids and not errors:
        return {
            "deleted": True,
            "already_deleted": True,
            "storage_ids": [],
            "mount_path": mount_path,
            "errors": [],
        }

    for sid in sorted(set(target_ids)):
        try:
            openlist_client.delete_storage(config.OPENLIST_ADMIN_PASSWORD, sid)
            deleted.append(str(sid))
        except Exception as exc:
            if _openlist_targets_absent(openlist_client, config.OPENLIST_ADMIN_PASSWORD, target_mounts):
                logger.info("OpenList storage already removed after delete error: id=%s error=%s", sid, exc)
                deleted.append(str(sid))
                continue
            logger.warning("Delete OpenList storage failed: id=%s error=%s", sid, exc)
            errors.append(f"{sid}: {exc}")

    return {
        "deleted": bool(deleted) and not errors,
        "storage_ids": deleted,
        "mount_path": mount_path,
        "errors": errors,
    }


def _create_openlist_storage_for_source(source: dict[str, Any]) -> dict[str, Any]:
    ok, message, ready_data = _check_openlist_ready(require_enabled=True)
    if not ok:
        return {"created": False, "message": message}

    AppConfig = _get_app_config_class()
    _, openlist_client = _get_openlist_client()

    config = AppConfig()
    config.load_config()
    password = config.OPENLIST_ADMIN_PASSWORD
    base_url = ready_data["base_url"]
    openlist_client.set_base_url(base_url)

    driver = _label_to_driver(str(source.get("driver") or ""))
    mount_path = _normalize_mount_path(source.get("mount_path") or _public_openlist_mount_path(driver))

    addition = _apply_openlist_driver_defaults(driver, source.get("addition") or {})
    missing = _missing_openlist_addition(driver, addition)
    if missing:
        return {"created": False, "message": f"缺少 {missing}"}

    storage_config = {
        "driver": driver,
        "mount_path": mount_path,
        "addition": addition,
        "order": int(source.get("order") or 0),
        "cache_expiration": int(source.get("cache_expiration") or 30),
    }

    result = openlist_client.add_storage(password, storage_config)
    if result.get("code") != 200:
        return {"created": False, "message": result.get("message", "OpenList storage mount failed")}

    storage_data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    storage_id = str(storage_data.get("id", ""))

    sources = source_service.load_sources()
    for index, item in enumerate(sources):
        if item.get("id") == source.get("id"):
            sources[index]["storage_id"] = storage_id
            break
    source_service.save_sources(sources)

    return {
        "created": True,
        "storage_id": storage_id,
        "mount_path": mount_path,
    }


def _normalize_openlist_source_mount(
    body: dict[str, Any],
    existing: dict[str, Any] | None,
    selected_paths: list[str],
    driver: str,
) -> str:
    raw_mount = body.get("mount_path") or body.get("mountPath") or (existing or {}).get("mount_path") or ""
    try:
        mount_path = _normalize_mount_path(raw_mount)
    except ValueError:
        mount_path = ""

    if mount_path and not _is_preview_mount_path(mount_path) and mount_path.lower() not in {"/", "/openlist"}:
        return mount_path

    for path in selected_paths:
        normalized = "/" + str(path or "").strip("/")
        parts = [part for part in normalized.split("/") if part]
        if parts:
            return "/" + parts[0]

    fallback = _public_openlist_mount_path(driver)
    if fallback.lower() in {"/", "/openlist"}:
        fallback = "/openlist"
    return fallback


def _openlist_targets_absent(openlist_client, password: str, mount_paths: set[str]) -> bool:
    if not mount_paths:
        return False
    try:
        storages = openlist_client.list_storages(password)
    except Exception as exc:
        logger.warning("Verify OpenList storage deletion failed: %s", exc)
        return False
    existing_mounts = {_normalize_mount_path(item.get("mount_path") or "/") for item in storages}
    return all(path not in existing_mounts for path in mount_paths)


def _delete_openlist_preview_storage(openlist_client, password: str, driver: str) -> dict[str, Any]:
    preview_mount = _preview_mount_path(driver)
    deleted: list[str] = []
    errors: list[str] = []
    try:
        storages = openlist_client.list_storages(password)
    except Exception as exc:
        logger.warning("List OpenList storages failed before preview cleanup: %s", exc)
        return {"deleted": False, "mount_path": preview_mount, "errors": [str(exc)]}

    for storage in storages:
        storage_mount = _normalize_mount_path(storage.get("mount_path") or "/")
        if storage_mount != preview_mount:
            continue
        sid = storage.get("id")
        if sid is None:
            errors.append(f"Missing storage id for {storage_mount}")
            continue
        try:
            openlist_client.delete_storage(password, int(sid))
            deleted.append(str(sid))
        except Exception as exc:
            if _openlist_targets_absent(openlist_client, password, {preview_mount}):
                logger.info("OpenList preview storage already removed after delete error: id=%s error=%s", sid, exc)
                deleted.append(str(sid))
                continue
            logger.warning("Delete OpenList preview storage failed: id=%s mount=%s error=%s", sid, storage_mount, exc)
            errors.append(f"{sid}: {exc}")

    return {"deleted": bool(deleted) and not errors, "storage_ids": deleted, "mount_path": preview_mount, "errors": errors}


def _cleanup_openlist_orphan_storages(openlist_client, password: str) -> dict[str, Any]:
    active_mounts = {
        _normalize_mount_path(source.get("mount_path") or _public_openlist_mount_path(_label_to_driver(str(source.get("driver") or ""))))
        for source in source_service.load_sources()
        if source.get("type") == "openlist"
    }
    deleted: list[dict[str, Any]] = []
    kept: list[str] = []
    errors: list[str] = []

    try:
        storages = openlist_client.list_storages(password)
    except Exception as exc:
        return {"deleted": deleted, "kept": kept, "errors": [str(exc)]}

    for storage in storages:
        sid = storage.get("id")
        mount_path = _normalize_mount_path(storage.get("mount_path") or "/")
        should_delete = _is_preview_mount_path(mount_path) or (
            mount_path not in active_mounts and mount_path != "/"
        )
        if not should_delete:
            kept.append(mount_path)
            continue
        if sid is None:
            errors.append(f"Missing storage id for {mount_path}")
            continue
        try:
            openlist_client.delete_storage(password, int(sid))
            deleted.append({"id": sid, "mount_path": mount_path})
        except Exception as exc:
            if _openlist_targets_absent(openlist_client, password, {mount_path}):
                logger.info("OpenList storage already removed during cleanup: id=%s mount=%s error=%s", sid, mount_path, exc)
                deleted.append({"id": sid, "mount_path": mount_path})
                continue
            logger.warning("Cleanup OpenList storage failed: id=%s mount=%s error=%s", sid, mount_path, exc)
            errors.append(f"{mount_path}: {exc}")

    return {"deleted": deleted, "kept": kept, "errors": errors}


def _maybe_start_scan(source: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    if not _coerce_bool(body.get("auto_scan", body.get("autoScan", True))):
        return scan_service.get_status(source["id"])
    return scan_service.start_background_scan(source["id"])


def _normalized_selected_paths(values: Any) -> tuple[str, ...]:
    paths = _coerce_path_list(values)
    normalized = {
        ("/" if str(path or "").strip() == "/" else str(path or "").strip().replace("\\", "/").rstrip("/")).casefold()
        for path in paths
        if str(path or "").strip()
    }
    return tuple(sorted(normalized))


def _build_webdav_base_url(data: dict[str, Any]) -> str:
    raw = str(data.get("host") or data.get("path") or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        base = raw.rstrip("/")
    else:
        protocol = str(data.get("protocol") or "http").strip() or "http"
        base = f"{protocol}://{raw.strip('/')}"
    port = str(data.get("port") or "").strip()
    host_part = base.split("://", 1)[-1]
    if port and ":" not in host_part.split("/", 1)[0]:
        scheme, rest = base.split("://", 1)
        base = f"{scheme}://{rest.split('/', 1)[0]}:{port}" + ("/" + rest.split("/", 1)[1] if "/" in rest else "")
    return base.rstrip("/")


def _resolve_webdav_base_url(data: dict[str, Any]) -> tuple[str, str]:
    """Return the first working WebDAV base URL, trying /dav for OpenList/AList-style servers."""
    WebDAVClient = _get_webdav_client_class()

    username = str(data.get("username") or "")
    password = str(data.get("password") or "")
    base = _build_webdav_base_url(data)
    if not base:
        return "", "Missing WebDAV address"

    candidates = [base]
    parsed = urlparse(base)
    if not parsed.path or parsed.path == "/":
        candidates.append(base.rstrip("/") + "/dav")

    last_error = ""
    for candidate in dict.fromkeys(candidates):
        try:
            client = WebDAVClient(host=candidate, username=username, password=password)
            if client.verify_connection():
                return candidate, ""
            last_error = "WebDAV connection failed"
        except Exception as exc:
            last_error = str(exc)

    return "", last_error or "WebDAV connection failed"


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() not in {"", "0", "false", "no", "off", "none"}


def _coerce_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in re.split(r"[,;\n]", text) if part.strip()]


def _coerce_addition(body: dict[str, Any]) -> dict[str, Any]:
    addition = body.get("addition", {})
    if isinstance(addition, str):
        try:
            addition = json.loads(addition) if addition.strip() else {}
        except json.JSONDecodeError:
            addition = {}
    if not isinstance(addition, dict):
        addition = {}

    known_fields = {
        "cookie",
        "refresh_token",
        "root_folder_id",
        "root_folder_path",
        "root_path",
        "drive_type",
        "base_url",
        "token",
        "use_online_api",
        "api_url_address",
        "client_id",
        "client_secret",
        "download_api",
        "custom_crack_ua",
        "upload_thread",
        "upload_api",
        "only_list_video_file",
        "address",
        "username",
        "password",
    }
    for field in known_fields:
        if field in body and str(body.get(field) or "").strip():
            key = "root_folder_id" if field == "root_path" else field
            addition[key] = str(body[field]).strip()

    if "cookie" in addition and isinstance(addition["cookie"], str):
        addition["cookie"] = addition["cookie"].strip()
        if addition["cookie"].lower().startswith("cookie:"):
            addition["cookie"] = addition["cookie"].split(":", 1)[1].strip()
    if "root_folder_id" not in addition and "root_folder_path" not in addition:
        addition["root_folder_id"] = "0"
    return addition


def _coerce_openlist_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _apply_openlist_driver_defaults(driver: str, addition: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(addition or {})
    if driver == "BaiduNetdisk":
        normalized.pop("cookie", None)
        if "root_folder_id" in normalized and "root_folder_path" not in normalized:
            root_folder = str(normalized.pop("root_folder_id") or "").strip()
            normalized["root_folder_path"] = "/" if root_folder in {"", "0"} else root_folder
        normalized.setdefault("root_folder_path", "/")
        normalized.setdefault("order_by", "name")
        normalized.setdefault("order_direction", "asc")
        normalized.setdefault("download_api", "official")
        normalized["use_online_api"] = _coerce_openlist_bool(normalized.get("use_online_api", True))
        normalized.setdefault("api_url_address", "https://api.oplist.org/baiduyun/renewapi")
        normalized.setdefault("client_id", "")
        normalized.setdefault("client_secret", "")
        normalized.setdefault("custom_crack_ua", "netdisk")
        normalized.setdefault("upload_thread", "3")
        normalized.setdefault("upload_api", "https://d.pcs.baidu.com")
        normalized.setdefault("custom_upload_part_size", 0)
        normalized.setdefault("low_bandwith_upload_mode", False)
        normalized.setdefault("only_list_video_file", False)
    return normalized


def _normalize_mount_path(value: Any) -> str:
    mount_path = str(value or "").strip()
    if not mount_path:
        raise ValueError("Missing mount path")
    if not mount_path.startswith("/"):
        mount_path = "/" + mount_path
    return mount_path.rstrip("/") or "/"


def _openlist_selected_paths(paths: list[str], mount_path: str) -> list[str]:
    mount = _normalize_mount_path(mount_path)
    if not paths:
        return []

    result = []
    for raw_path in paths:
        path = "/" + str(raw_path or "").strip("/")
        duplicate_prefix = mount.rstrip("/") + mount
        if path == duplicate_prefix:
            path = mount
        elif path.startswith(duplicate_prefix + "/"):
            path = mount.rstrip("/") + path[len(duplicate_prefix):]
        if path == "/":
            normalized = mount
        elif path == mount or path.startswith(mount + "/"):
            normalized = path
        else:
            normalized = mount.rstrip("/") + path
        if normalized not in result:
            result.append(normalized)
    return result or []


def _label_to_driver(label: str) -> str:
    value = str(label or "").strip()
    if not value:
        return ""
    for item in _supported_openlist_drivers():
        if item.get("driver") == value or item.get("label") == value:
            return item.get("driver", "")
    lowered = value.lower()
    aliases = {
        "quark": "Quark",
        "aliyun": "AliyundriveOpen",
        "ali": "AliyundriveOpen",
        "115": "115 Cloud",
        "baidu": "BaiduNetdisk",
        "webdav": "WebDav",
    }
    return aliases.get(lowered, value)


def _supported_openlist_drivers() -> list[dict[str, Any]]:
    return [
        {
            "driver": "Quark",
            "label": "夸克网盘",
            "fields": [
                {"key": "cookie", "label": "Cookie", "type": "textarea", "required": True},
                {"key": "root_folder_id", "label": "Root Folder ID", "placeholder": "0"},
            ],
        },
        {
            "driver": "AliyundriveOpen",
            "label": "阿里云盘 Open",
            "fields": [
                {"key": "refresh_token", "label": "Refresh Token", "required": True},
                {"key": "root_folder_id", "label": "Root Folder ID", "placeholder": "0"},
                {"key": "drive_type", "label": "Drive Type", "placeholder": "default"},
            ],
        },
        {
            "driver": "115 Cloud",
            "label": "115 网盘",
            "fields": [
                {"key": "cookie", "label": "Cookie", "type": "textarea", "required": True},
                {"key": "root_folder_id", "label": "Root Folder ID", "placeholder": "0"},
            ],
        },
        {
            "driver": "BaiduNetdisk",
            "label": "百度网盘",
            "fields": [
                {"key": "refresh_token", "label": "Refresh Token", "required": True},
                {"key": "root_folder_path", "label": "Root Folder Path", "placeholder": "/"},
            ],
        },
        {
            "driver": "WebDav",
            "label": "WebDAV",
            "fields": [
                {"key": "address", "label": "Address", "required": True},
                {"key": "username", "label": "Username"},
                {"key": "password", "label": "Password", "type": "password"},
                {"key": "root_folder_path", "label": "Root Folder Path", "placeholder": "/"},
            ],
        },
    ]


def _openlist_drivers_for_api() -> list[dict[str, Any]]:
    """Return driver metadata with frontend-compatible keys."""
    name_map = {
        "Quark": "quark",
        "AliyundriveOpen": "aliyun",
        "115 Cloud": "115",
        "BaiduNetdisk": "baidu",
        "WebDav": "webdav",
    }
    icon_map = {
        "Quark": "folder",
        "AliyundriveOpen": "folder",
        "115 Cloud": "folder",
        "BaiduNetdisk": "folder",
        "WebDav": "folder",
    }
    result = []
    for item in _supported_openlist_drivers():
        driver = item.get("driver", "")
        frontend_name = name_map.get(driver, str(driver).lower())
        result.append({
            **item,
            "name": frontend_name,
            "value": frontend_name,
            "icon": icon_map.get(driver, "folder"),
            "disabled": False,
        })
    return result


def _check_openlist_ready(require_enabled: bool = False) -> tuple[bool, str, dict[str, Any]]:
    AppConfig = _get_app_config_class()
    openlist_manager = _get_openlist_manager()

    config = AppConfig()
    config.load_config()
    if require_enabled and not config.OPENLIST_ENABLED:
        return False, "Please enable built-in OpenList in settings", {}
    status = openlist_manager.get_status()
    if status.get("status") != "running":
        return False, "Please start the built-in OpenList service", status
    if not status.get("logged_in"):
        login_result = openlist_manager.ensure_logged_in()
        status = openlist_manager.get_status()
        if not login_result.get("success") or not status.get("logged_in"):
            return False, f"OpenList is not logged in: {login_result.get('message', '')}", status
    if not config.OPENLIST_ADMIN_PASSWORD:
        return False, "Missing OpenList admin password", status
    data = dict(status)
    data["base_url"] = status.get("base_url") or f"http://127.0.0.1:{status.get('port', 5244)}"
    return True, "ok", data


def _browse_openlist(path: str = "/", page: int = 1, per_page: int = 100):
    ok, message, data = _check_openlist_ready()
    if not ok:
        return api_response(code=400, message=message, data={"path": path, "items": [], "ok": False})
    AppConfig = _get_app_config_class()
    _, openlist_client = _get_openlist_client()

    config = AppConfig()
    config.load_config()
    openlist_client.set_base_url(data["base_url"])
    result = openlist_client.list_files(config.OPENLIST_ADMIN_PASSWORD, path, page, per_page)
    if result.get("code") != 200:
        return api_response(code=500, message=result.get("message", "OpenList browse failed"), data={"path": path, "items": [], "ok": False})

    items = result.get("data", {}).get("content", []) or []
    for item in items:
        item["isDir"] = scan_service._openlist_is_dir(item)
        item["path"] = scan_service._openlist_entry_path(path, item)
    return api_response(data={"path": path, "items": items, "ok": True, "raw": result})


def restore_openlist_sources() -> None:
    ok, message, data = _check_openlist_ready()
    if not ok:
        logger.warning("Skip OpenList source recovery: %s", message)
        return

    AppConfig = _get_app_config_class()
    _, openlist_client = _get_openlist_client()
    config = AppConfig()
    config.load_config()
    openlist_client.set_base_url(data["base_url"])

    storages = openlist_client.list_storages(config.OPENLIST_ADMIN_PASSWORD)
    mounted_paths = {str(item.get("mount_path") or "") for item in storages}
    for source in source_service.load_sources():
        if source.get("type") != "openlist":
            continue
        driver = _label_to_driver(str(source.get("driver") or ""))
        mount_path = _normalize_mount_path(source.get("mount_path") or _public_openlist_mount_path(driver))
        if mount_path not in mounted_paths:
            logger.warning("Saved OpenList source mount not found: %s", mount_path)


def _browse_openlist_preview(body: dict[str, Any], path: str = "/", page: int = 1, per_page: int = 100):
    try:
        ok, message, data = _check_openlist_ready(require_enabled=True)
        if not ok:
            return api_response(code=400, message=message, data={"path": path, "items": [], "ok": False})

        AppConfig = _get_app_config_class()
        SUPPORTED_DRIVERS, openlist_client = _get_openlist_client()

        driver = _label_to_driver(str(body.get("driver_type") or body.get("driver") or ""))
        valid_drivers = {item.get("driver") for item in SUPPORTED_DRIVERS}
        if driver not in valid_drivers:
            return api_response(code=400, message=f"Unsupported cloud drive type: {body.get('driver') or ''}", data={"path": path, "items": [], "ok": False})

        addition = _coerce_addition(body)
        addition = _merge_saved_openlist_addition(addition, body, driver)
        addition = _apply_openlist_driver_defaults(driver, addition)
        missing = _missing_openlist_addition(driver, addition)
        if missing:
            return api_response(code=400, message=f"Missing {missing}", data={"path": path, "items": [], "ok": False})

        config = AppConfig()
        config.load_config()
        openlist_client.set_base_url(data["base_url"])

        public_mount = _normalize_mount_path(body.get("mount_path") or body.get("mountPath") or _public_openlist_mount_path(driver))
        if _is_preview_mount_path(public_mount) or public_mount.lower() in {"/openlist", "/"}:
            public_mount = _public_openlist_mount_path(driver)
        path = _replace_preview_mount(path, _preview_mount_path(driver), public_mount)
        public_path = _normalize_preview_public_path(path, public_mount)
        saved_source = _find_saved_openlist_source(body, driver, public_mount)
        has_new_credentials = _body_has_openlist_credentials(body)
        if saved_source and not has_new_credentials:
            return _browse_existing_openlist_source(
                openlist_client=openlist_client,
                password=config.OPENLIST_ADMIN_PASSWORD,
                source=saved_source,
                driver=driver,
                public_mount=public_mount,
                public_path=public_path,
                page=page,
                per_page=per_page,
            )
        if not has_new_credentials and _openlist_mount_exists(openlist_client, config.OPENLIST_ADMIN_PASSWORD, public_mount):
            return _browse_existing_openlist_source(
                openlist_client=openlist_client,
                password=config.OPENLIST_ADMIN_PASSWORD,
                source={},
                driver=driver,
                public_mount=public_mount,
                public_path=public_path,
                page=page,
                per_page=per_page,
            )
        storage_mount = "" if has_new_credentials else _find_openlist_storage_mount(openlist_client, config.OPENLIST_ADMIN_PASSWORD, driver, public_mount)
        if storage_mount:
            public_path = _normalize_preview_public_path(path, storage_mount)
            return _browse_existing_openlist_source(
                openlist_client=openlist_client,
                password=config.OPENLIST_ADMIN_PASSWORD,
                source={},
                driver=driver,
                public_mount=storage_mount,
                public_path=public_path,
                page=page,
                per_page=per_page,
            )
        preview_mount = _preview_mount_path(driver)
        storage_config = {
            "driver": driver,
            "mount_path": preview_mount,
            "addition": addition,
            "order": -100,
            "cache_expiration": 0,
        }
        result = openlist_client.add_storage(config.OPENLIST_ADMIN_PASSWORD, storage_config)
        if result.get("code") != 200:
            return api_response(code=500, message=result.get("message", "OpenList preview mount failed"), data={"path": path, "items": [], "ok": False})

        relative_suffix = public_path[len(public_mount):].strip("/")
        actual_path = preview_mount if not relative_suffix else preview_mount.rstrip("/") + "/" + relative_suffix
        list_result = openlist_client.list_files(config.OPENLIST_ADMIN_PASSWORD, actual_path, page, per_page, refresh=True)
        if list_result.get("code") != 200:
            return api_response(code=500, message=list_result.get("message", "OpenList browse failed"), data={"path": public_path, "items": [], "ok": False})

        items = list_result.get("data", {}).get("content", []) or []
        normalized_items = []
        for item in items:
            item["isDir"] = scan_service._openlist_is_dir(item)
            actual_item_path = scan_service._openlist_entry_path(actual_path, item)
            item["path"] = _replace_preview_mount(actual_item_path, preview_mount, public_mount)
            normalized_items.append(item)
        return api_response(data={"path": public_path, "items": normalized_items, "ok": True, "preview_mount": preview_mount})
    except Exception as exc:
        logger.exception("Browse OpenList preview failed")
        return api_response(code=500, message=str(exc), data={"path": path, "items": [], "ok": False})


def _preview_mount_path(driver: str) -> str:
    aliases = {
        "Quark": "quark",
        "AliyundriveOpen": "aliyun",
        "115 Cloud": "115",
        "BaiduNetdisk": "baidu",
        "WebDav": "webdav",
    }
    return f"/__preview_{aliases.get(driver, driver.lower().replace(' ', '_'))}"


def _public_openlist_mount_path(driver: str) -> str:
    aliases = {
        "Quark": "quark",
        "AliyundriveOpen": "aliyun",
        "115 Cloud": "115",
        "BaiduNetdisk": "baidu",
        "WebDav": "webdav",
    }
    return "/" + aliases.get(driver, driver.lower().replace(" ", "_"))


def _normalize_preview_public_path(path: str, public_mount: str) -> str:
    public_mount = _normalize_mount_path(public_mount)
    normalized = "/" + str(path or "/").strip("/")
    duplicate_prefix = public_mount.rstrip("/") + public_mount
    if normalized == duplicate_prefix:
        normalized = public_mount
    elif normalized.startswith(duplicate_prefix + "/"):
        normalized = public_mount.rstrip("/") + normalized[len(duplicate_prefix):]
    if normalized.lower() in {"/", "/.", "/openlist"}:
        return public_mount
    if normalized == public_mount or normalized.startswith(public_mount + "/"):
        return normalized
    return public_mount.rstrip("/") + normalized


def _replace_preview_mount(path: str, preview_mount: str, public_mount: str) -> str:
    normalized = "/" + str(path or "").strip("/")
    preview = "/" + str(preview_mount or "").strip("/")
    public = _normalize_mount_path(public_mount)
    if normalized == preview:
        return public
    if normalized.startswith(preview + "/"):
        return public.rstrip("/") + normalized[len(preview):]
    return normalized


def _is_preview_mount_path(path: str) -> bool:
    return _normalize_mount_path(path).startswith("/__preview_")


def _openlist_mount_exists(openlist_client, password: str, mount_path: str) -> bool:
    try:
        normalized = _normalize_mount_path(mount_path)
        return any(
            _normalize_mount_path(item.get("mount_path") or "/") == normalized
            and not _is_preview_mount_path(item.get("mount_path") or "/")
            for item in openlist_client.list_storages(password)
        )
    except Exception as exc:
        logger.warning("Check OpenList mount failed: mount=%s error=%s", mount_path, exc)
        return False


def _find_openlist_storage_mount(openlist_client, password: str, driver: str, preferred_mount: str = "") -> str:
    try:
        storages = openlist_client.list_storages(password)
    except Exception as exc:
        logger.warning("Read OpenList storage list failed: %s", exc)
        return ""

    normalized_preferred = _normalize_mount_path(preferred_mount or _public_openlist_mount_path(driver))
    fallback = ""
    for item in storages:
        item_mount = _normalize_mount_path(item.get("mount_path") or "/")
        if _is_preview_mount_path(item_mount):
            continue
        item_driver = _label_to_driver(str(item.get("driver") or ""))
        if item_mount == normalized_preferred:
            return item_mount
        if not fallback and item_driver == driver:
            fallback = item_mount
    return fallback


def _browse_existing_openlist_source(
    openlist_client,
    password: str,
    source: dict[str, Any],
    driver: str,
    public_mount: str,
    public_path: str,
    page: int,
    per_page: int,
):
    public_mount = _normalize_mount_path(public_mount)
    public_path = _normalize_preview_public_path(public_path, public_mount)

    try:
        result = openlist_client.list_files(password, public_path, page, per_page, refresh=True)
        return _openlist_browse_response(public_path, result)
    except Exception as exc:
        if _is_openlist_guest_error(exc):
            return api_response(
                data={"path": public_mount, "items": [], "ok": False, "needOpenListLogin": True},
                message="OpenList storage credential expired, please update credentials",
            )
        if "object not found" not in str(exc).lower():
            raise
        logger.warning("OpenList path not found, falling back to mount root: path=%s mount=%s", public_path, public_mount)

    try:
        result = openlist_client.list_files(password, public_mount, page, per_page, refresh=True)
        return _openlist_browse_response(
            public_mount,
            result,
            message=f"Directory not found, returned {public_mount}",
        )
    except Exception as exc:
        if _is_openlist_guest_error(exc):
            return api_response(
                data={"path": public_mount, "items": [], "ok": False, "needOpenListLogin": True},
                message="OpenList storage credential expired, please update credentials",
            )
        if "object not found" not in str(exc).lower():
            raise
        return api_response(
            data={"path": public_mount, "items": [], "ok": True, "missingPath": public_path},
            message=f"Mount {public_mount} is empty or not refreshed yet",
        )


def _ensure_openlist_storage_ready(openlist_client, password: str, source: dict[str, Any], driver: str, public_mount: str) -> None:
    addition = _source_openlist_addition(source)
    if not _has_openlist_credentials(driver, addition):
        addition = _merge_saved_openlist_addition(addition, {"id": source.get("id"), "mount_path": public_mount}, driver)
    addition = _apply_openlist_driver_defaults(driver, addition)
    if driver in {"Quark", "115 Cloud"} and not str(addition.get("root_folder_id") or addition.get("root_folder_path") or "").strip():
        addition["root_folder_id"] = "0"
    storage_config = {
        "driver": driver,
        "mount_path": public_mount,
        "addition": addition,
        "order": 0,
        "cache_expiration": 30,
    }
    try:
        openlist_client.add_storage(password, storage_config)
    except Exception as exc:
        if _is_openlist_guest_error(exc) and _replace_openlist_storage(openlist_client, password, storage_config):
            return
        logger.warning("Refresh OpenList mount failed, continuing browse: mount=%s error=%s", public_mount, exc)


def _replace_openlist_storage(openlist_client, password: str, storage_config: dict[str, Any]) -> bool:
    mount_path = storage_config.get("mount_path", "")
    try:
        for storage in openlist_client.list_storages(password):
            if storage.get("mount_path") == mount_path and storage.get("id") is not None:
                openlist_client.delete_storage(password, int(storage["id"]))
                logger.info("Deleted invalid OpenList mount and will rebuild: %s", mount_path)
                break
        openlist_client.add_storage(password, storage_config)
        logger.info("Rebuilt OpenList mount: %s", mount_path)
        return True
    except Exception as exc:
        logger.warning("Rebuild OpenList mount failed: mount=%s error=%s", mount_path, exc)
        return False


def _is_openlist_guest_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "require login [guest]" in text
        or ("require login" in text and "guest" in text)
        or "user not login" in text
        or "login timeout" in text
        or "登录超时" in str(exc)
    )


def _ensure_openlist_storage(openlist_client, password: str, source: dict[str, Any], driver: str, public_mount: str) -> None:
    addition = _source_openlist_addition(source)
    if not _has_openlist_credentials(driver, addition):
        addition = _merge_saved_openlist_addition(addition, {"id": source.get("id"), "mount_path": public_mount}, driver)
    addition = _apply_openlist_driver_defaults(driver, addition)
    storage_config = {
        "driver": driver,
        "mount_path": public_mount,
        "addition": addition,
        "order": 0,
        "cache_expiration": 30,
    }
    try:
        openlist_client.add_storage(password, storage_config)
    except Exception as exc:
        logger.warning("Refresh OpenList mount failed, continuing browse: mount=%s error=%s", public_mount, exc)


def _source_openlist_addition(source: dict[str, Any]) -> dict[str, Any]:
    addition = source.get("addition") or {}
    if isinstance(addition, str):
        try:
            addition = json.loads(addition) if addition.strip() else {}
        except json.JSONDecodeError:
            addition = {}
    if not isinstance(addition, dict):
        addition = {}
    addition = dict(addition)
    cookie = str(source.get("cookie") or "").strip()
    if cookie and str(addition.get("cookie") or "").strip() in {"", "******"}:
        addition["cookie"] = cookie
    return addition


def _openlist_browse_response(path: str, result: dict[str, Any], message: str = "ok"):
    if result.get("code") != 200:
        return api_response(code=500, message=result.get("message", "OpenList browse failed"), data={"path": path, "items": [], "ok": False})
    items = result.get("data", {}).get("content", []) or []
    for item in items:
        item["isDir"] = scan_service._openlist_is_dir(item)
        item["path"] = scan_service._openlist_entry_path(path, item)
    return api_response(message=message, data={"path": path, "items": items, "ok": True, "raw": result})


def _strip_preview_mount(path: str, mount_path: str) -> str:
    normalized = "/" + str(path or "").strip("/")
    mount = "/" + str(mount_path or "").strip("/")
    if normalized == mount:
        return "/"
    if normalized.startswith(mount + "/"):
        stripped = normalized[len(mount):]
        return stripped or "/"
    return normalized


def _missing_openlist_addition(driver: str, addition: dict[str, Any]) -> str:
    if driver in {"Quark", "115 Cloud"} and not str(addition.get("cookie") or "").strip():
        return "Cookie"
    if driver in {"AliyundriveOpen", "BaiduNetdisk"} and not str(addition.get("refresh_token") or "").strip():
        return "Refresh Token"
    if driver == "WebDav" and not str(addition.get("address") or "").strip():
        return "WebDAV address"
    return ""


def _merge_saved_openlist_addition(addition: dict[str, Any], body: dict[str, Any], driver: str) -> dict[str, Any]:
    """Reuse saved OpenList credentials when editing an existing source."""
    merged = dict(addition or {})
    sensitive_keys = {"cookie", "refresh_token", "token", "password"}
    for key in list(sensitive_keys):
        if str(merged.get(key) or "").strip() == "******":
            merged.pop(key, None)

    if _has_openlist_credentials(driver, merged):
        return merged

    source_id = str(body.get("source_id") or body.get("sourceId") or body.get("id") or "").strip()
    mount_path = str(body.get("mount_path") or body.get("mountPath") or "").strip()
    source = _find_saved_openlist_source(
        {"source_id": source_id, "mount_path": mount_path},
        driver,
        mount_path,
    )

    if not source:
        return merged

    saved_addition = source.get("addition") or {}
    if isinstance(saved_addition, str):
        try:
            saved_addition = json.loads(saved_addition) if saved_addition.strip() else {}
        except json.JSONDecodeError:
            saved_addition = {}
    if not isinstance(saved_addition, dict):
        saved_addition = {}

    for key, value in saved_addition.items():
        if key in sensitive_keys and str(merged.get(key) or "").strip():
            continue
        if key in sensitive_keys or key not in merged or str(merged.get(key) or "").strip() in {"", "******"}:
            merged[key] = value

    cookie = str(source.get("cookie") or "").strip()
    if cookie and not str(merged.get("cookie") or "").strip():
        merged["cookie"] = cookie
    password = str(source.get("password") or "").strip()
    if password and not str(merged.get("password") or "").strip():
        merged["password"] = password
    return merged


def _find_saved_openlist_source(body: dict[str, Any], driver: str, mount_path: str = "") -> dict[str, Any] | None:
    source_id = str(body.get("source_id") or body.get("sourceId") or body.get("id") or "").strip()
    normalized_mount = _normalize_mount_path(mount_path or body.get("mount_path") or body.get("mountPath") or _public_openlist_mount_path(driver))
    candidates = source_service.load_sources()

    if source_id:
        source = next((item for item in candidates if item.get("id") == source_id), None)
        if source and source.get("type") == "openlist":
            return source

    source = next(
        (
            item for item in candidates
            if item.get("type") == "openlist"
            and _label_to_driver(str(item.get("driver") or "")) == driver
            and _normalize_mount_path(item.get("mount_path") or _public_openlist_mount_path(driver)) == normalized_mount
        ),
        None,
    )
    if source:
        return source

    matching = [
        item for item in candidates
        if item.get("type") == "openlist" and _label_to_driver(str(item.get("driver") or "")) == driver
    ]
    return matching[0] if len(matching) == 1 else None


def _body_has_openlist_credentials(body: dict[str, Any]) -> bool:
    addition = body.get("addition") or {}
    if isinstance(addition, str):
        try:
            addition = json.loads(addition) if addition.strip() else {}
        except json.JSONDecodeError:
            addition = {}
    if not isinstance(addition, dict):
        addition = {}
    for key in ("cookie", "refresh_token", "token", "password"):
        value = str(body.get(key) or addition.get(key) or "").strip()
        if value and value != "******":
            return True
    return False


def _has_openlist_credentials(driver: str, addition: dict[str, Any]) -> bool:
    if driver in {"Quark", "115 Cloud"}:
        return bool(str(addition.get("cookie") or "").strip())
    if driver in {"AliyundriveOpen", "BaiduNetdisk"}:
        return bool(str(addition.get("refresh_token") or "").strip())
    if driver == "WebDav":
        return bool(str(addition.get("address") or "").strip())
    return True


def _list_local_directory(path: str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists() or not target.is_dir():
        return []
    items = []
    for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        items.append({
            "name": child.name,
            "type": "folder" if child.is_dir() else "file",
            "path": str(child.resolve()),
            "isDir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else 0,
        })
    return items


def _set_favorite(movie_id: str, favorite: bool):
    movies = lib.load_library()
    found = False
    for movie in movies:
        if movie.get("id") == movie_id:
            movie["is_favorite"] = favorite
            found = True
            break
    if not found:
        return api_response(code=404, message="Movie not found")
    lib.save_library(movies)
    try:
        analytics_service.record_event({"event_type": "favorite_add" if favorite else "favorite_remove", "movie_id": movie_id})
    except Exception as exc:
        logger.debug("Record favorite event failed: movie=%s error=%s", movie_id, exc)
    return api_response(data={"id": movie_id, "isFavorite": favorite})


# ==================== 后台任务（jobs）====================

@router.get("/api/jobs/status")
def jobs_status():
    """返回所有后台任务进度。前端引导页轮询此接口。"""
    return api_response(data=jobs_state.get_all())


def _run_pool_job(task: str, func):
    """启动一个后台线程执行任务，避免阻塞 HTTP 请求。"""
    if jobs_state.is_running(task):
        return api_response(message="任务正在进行中", data=jobs_state.get(task))
    import threading
    t = threading.Thread(target=func, daemon=True, name=f"job-{task}")
    t.start()
    return api_response(data=jobs_state.get(task))


@router.post("/api/jobs/refresh/all")
def jobs_refresh_all():
    """手动触发全量拉取（首次下载或重置）。"""
    return _run_pool_job(tmdb_fetcher.TASK_INITIAL, tmdb_fetcher.fetch_initial_pool)


@router.post("/api/jobs/refresh/trending")
def jobs_refresh_trending():
    """手动触发 trending 刷新。"""
    return _run_pool_job(tmdb_fetcher.TASK_TRENDING, tmdb_fetcher.refresh_trending)


@router.post("/api/jobs/refresh/hotness")
def jobs_refresh_hotness():
    """手动触发热度快照（写 hotness_series 时间序列）。"""
    return _run_pool_job(tmdb_fetcher.TASK_HOTNESS, tmdb_fetcher.refresh_hotness)


@router.post("/api/jobs/backfill-genres")
def jobs_backfill_genres():
    """手动触发题材回填（重放列表计划，约 5~10 分钟，零详情额度）。"""
    return _run_pool_job(tmdb_fetcher.TASK_GENRE_BACKFILL, tmdb_fetcher.backfill_genres)


_CANCELABLE_TASKS = {
    tmdb_fetcher.TASK_INITIAL,
    tmdb_fetcher.TASK_TRENDING,
    tmdb_fetcher.TASK_HOTNESS,
    tmdb_fetcher.TASK_GENRE_BACKFILL,
}


@router.post("/api/jobs/cancel/{task}")
def jobs_cancel(task: str):
    """请求取消正在运行的后台任务（任务在每轮循环检测取消标志后自行结束，已写入数据保留）。"""
    if task not in _CANCELABLE_TASKS:
        return api_response(code=400, message="未知任务", data=None)
    if not jobs_state.is_running(task):
        return api_response(message="任务未在运行", data=jobs_state.get(task))
    jobs_state.request_cancel(task)
    return api_response(message="已请求取消", data=jobs_state.get(task))


# ==================== 虚拟片库（pool）====================

def _pool_item_to_api(row: dict) -> dict:
    """把 metadata_pool 行归一化为前端 API 格式。"""
    import json as _json
    return {
        "id": row.get("id") or "",
        "source": row.get("source") or "",
        "externalId": row.get("external_id") or "",
        "mediaType": row.get("media_type") or "",
        "title": row.get("title") or "",
        "originalTitle": row.get("original_title") or "",
        "releaseDate": row.get("release_date") or "",
        "year": row.get("year"),
        "overview": row.get("overview") or "",
        "genres": _json.loads(row["genres"]) if row.get("genres") else [],
        "posterPath": row.get("poster_path") or "",
        "backdropPath": row.get("backdrop_path") or "",
        "voteAverage": row.get("vote_average"),
        "voteCount": row.get("vote_count"),
        "popularity": row.get("popularity"),
        "originCountry": _json.loads(row["origin_country"]) if row.get("origin_country") else [],
        "runtime": row.get("runtime"),
        "status": row.get("status") or "",
        "detailFetched": bool(row.get("detail_fetched")),
        "fetchedAt": row.get("fetched_at") or "",
        "updatedAt": row.get("updated_at") or "",
    }


@router.get("/api/pool/search")
def pool_search(q: str = "", sort: str = "popularity", media_type: str = "",
                page: int = 1, per_page: int = 20):
    """搜索虚拟片库（FTS5 全文检索 / 分页浏览）。"""
    rows = db_service.query_pool({
        "q": q, "sort": sort, "media_type": media_type,
        "page": page, "per_page": per_page,
    })
    total = db_service.pool_count(media_type=media_type or None, q=q or None)
    return api_response(data={
        "items": [_pool_item_to_api(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@router.get("/api/pool/trending")
def pool_trending(media_type: str = "", per_page: int = 20):
    """热门榜（按 popularity DESC）。"""
    rows = db_service.query_pool({"sort": "popularity", "media_type": media_type,
                                   "page": 1, "per_page": min(50, per_page)})
    return api_response(data={"items": [_pool_item_to_api(r) for r in rows]})


@router.get("/api/pool/top-rated")
def pool_top_rated(media_type: str = "", per_page: int = 20):
    """高分榜（按 vote_average DESC）。"""
    rows = db_service.query_pool({"sort": "vote_average", "media_type": media_type,
                                   "page": 1, "per_page": min(50, per_page)})
    return api_response(data={"items": [_pool_item_to_api(r) for r in rows]})


@router.get("/api/pool/count")
def pool_count_api():
    """返回虚拟片库总条数（引导页/看板用）。"""
    return api_response(data={"count": db_service.pool_count()})


@router.get("/api/pool/{pool_id}")
def pool_detail(pool_id: str):
    """虚拟片库条目详情（若未拉详情则懒加载补全）。"""
    item = tmdb_fetcher.fetch_detail(pool_id)
    if not item:
        return api_response(code=404, message="条目不存在")
    return api_response(data=_pool_item_to_api(item))


@router.post("/api/pool/{pool_id}/detail")
def pool_ensure_detail(pool_id: str):
    """手动触发详情懒加载补全。"""
    item = tmdb_fetcher.fetch_detail(pool_id)
    if not item:
        return api_response(code=404, message="条目不存在")
    return api_response(data=_pool_item_to_api(item))


def _hotness_row_to_api(row: dict) -> dict:
    """热度快照行 → 前端 API camelCase 格式。"""
    return {
        "poolId": row.get("pool_id") or "",
        "source": row.get("source") or "",
        "externalId": row.get("external_id") or "",
        "voteAverage": row.get("vote_average"),
        "voteCount": row.get("vote_count"),
        "popularity": row.get("popularity"),
        "collectionCount": row.get("collection_count"),
        "fetchedAt": row.get("fetched_at") or "",
    }


@router.get("/api/pool/{pool_id}/hotness")
def pool_hotness(pool_id: str, days: int = 30):
    """虚拟片库条目热度时间序列（近 N 天快照，按时间升序）。"""
    days = max(1, min(365, days))
    rows = db_service.get_hotness_series(pool_id, days)
    return api_response(data={
        "poolId": pool_id,
        "days": days,
        "items": [_hotness_row_to_api(r) for r in rows],
    })


@router.get("/api/pool/{pool_id}/similar")
def pool_similar(pool_id: str, limit: int = 12):
    """影视数据库相似推荐：同类型+同年代，按类型交集数+热度排序。"""
    limit = max(1, min(24, int(limit)))
    rows = db_service.find_similar_pool_items(pool_id, limit=limit)
    return api_response(data={"poolId": pool_id, "items": [_pool_item_to_api(r) for r in rows]})


# ==================== 想看清单（wishlist）====================

@router.get("/api/wishlist")
def wishlist_list():
    """想看清单列表（关联 metadata_pool 展示字段）。"""
    rows = db_service.list_wishlist()
    return api_response(data={"items": rows})


@router.get("/api/wishlist/{pool_id}")
def wishlist_check(pool_id: str):
    """检查某条目是否在想看清单中。"""
    return api_response(data={"poolId": pool_id, "inWishlist": db_service.in_wishlist(pool_id)})


@router.post("/api/wishlist/{pool_id}")
async def wishlist_add(pool_id: str, request: Request):
    """加入想看清单。"""
    try:
        body = await _parse_request_body(request)
        note = str(body.get("note", "") or "")
    except Exception:
        note = ""
    db_service.add_wishlist(pool_id, note)
    return api_response(data={"poolId": pool_id, "inWishlist": True}, message="已加入想看清单")


@router.delete("/api/wishlist/{pool_id}")
def wishlist_remove(pool_id: str):
    """从想看清单移除。"""
    removed = db_service.remove_wishlist(pool_id)
    return api_response(data={"poolId": pool_id, "inWishlist": False},
                        message="已移除" if removed else "不在清单中")


@router.get("/api/movies/{movie_id}/hotness")
def movie_hotness(movie_id: str, days: int = 30):
    """私有片库条目热度趋势。通过 tmdb_id 关联虚拟片库 (pool_id = tmdb:{tmdb_id})。"""
    movie = lib.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message="Movie not found")
    days = max(1, min(365, days))
    tmdb_id = str(movie.get("tmdb_id") or "").strip()
    if not tmdb_id:
        # 私有条目无 TMDB 关联 → 返回空序列，前端据此显示"无热度信号"
        return api_response(data={
            "movieId": movie_id,
            "poolId": "",
            "days": days,
            "linked": False,
            "items": [],
        })
    pool_id = f"tmdb:{tmdb_id}"
    rows = db_service.get_hotness_series(pool_id, days)
    return api_response(data={
        "movieId": movie_id,
        "poolId": pool_id,
        "days": days,
        "linked": True,
        "items": [_hotness_row_to_api(r) for r in rows],
    })


def _hotness_top_to_api(row: dict) -> dict:
    """Top 热度榜行 → camelCase（快照 + 池条目展示信息）。"""
    return {
        "poolId": row.get("pool_id") or "",
        "source": row.get("source") or "",
        "externalId": row.get("external_id") or "",
        "title": row.get("title") or "",
        "originalTitle": row.get("original_title") or "",
        "mediaType": row.get("media_type") or "",
        "posterPath": row.get("poster_path") or "",
        "year": row.get("year"),
        "voteAverage": row.get("vote_average"),
        "voteCount": row.get("vote_count"),
        "popularity": row.get("popularity"),
        "fetchedAt": row.get("fetched_at") or "",
    }


@router.get("/api/pool/hotness/top")
def pool_hotness_top(limit: int = 20):
    """虚拟片库热度 Top 榜：各条目最近一次快照按 popularity 降序。"""
    limit = max(1, min(100, limit))
    rows = db_service.get_top_hotness_by_popularity(limit)
    return api_response(data={"limit": limit, "items": [_hotness_top_to_api(r) for r in rows]})


# ==================== 发现推荐（recommend）====================

@router.get("/api/recommend/discover")
def recommend_discover(limit: int = 12, rerank: bool = False, refresh: bool = False):
    """基于虚拟片库热度 + 用户偏好的发现推荐。

    候选不限于用户已拥有影片；冷启动（本地无足够行为）时退化为纯热度推荐。
    每条带 reason 解释标签（正在热门/高分佳作/符合你的偏好/片库已有 等）。

    rerank=true 且 LLM_RERANK_ENABLED 开启时走 G2 AI 精排（超时/失败自动回退规则序，
    返回体 reranked=false）；refresh=true 强制绕过 24h 精排缓存。
    """
    if rerank:
        result = rerank_service.rerank_discover(limit, refresh=refresh)
    else:
        result = recommend_service.discover_recommendations(limit)
    return api_response(data=result)
