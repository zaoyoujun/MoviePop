"""System maintenance operations for settings actions."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig

try:
    from backend.services import db_service
    from backend.services.file_cache import get_cache
except ImportError:
    from services import db_service
    from services.file_cache import get_cache

logger = logging.getLogger(__name__)


CONFIG = AppConfig()
BASE_DIR = CONFIG.BASE_DIR
DATA_DIR = CONFIG.DATA_DIR
COVERS_DIR = CONFIG.COVERS_DIR


def clear_cache() -> dict[str, Any]:
    """Clear generated backend cache without deleting user settings or library data."""
    targets = [
        DATA_DIR / "cache",
        COVERS_DIR,
    ]
    deleted_bytes = 0
    deleted_items: list[str] = []
    errors: list[dict[str, str]] = []

    try:
        cache = get_cache()
        cache_dir = Path(cache.cache_dir).resolve()
        if _is_within(cache_dir, DATA_DIR.resolve()) and cache_dir not in targets:
            targets.append(cache_dir)
    except Exception as exc:
        logger.warning("Read file cache directory failed: %s", exc)

    for target in _unique_paths(targets):
        result = _remove_path(target)
        deleted_bytes += result["bytes"]
        if result["deleted"]:
            deleted_items.append(str(target))
        if result["error"]:
            errors.append({"path": str(target), "error": result["error"]})

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)

    return {
        "ok": not errors,
        "deleted": deleted_items,
        "deletedBytes": deleted_bytes,
        "errors": errors,
    }


def reset_application() -> dict[str, Any]:
    """Reset backend data and settings to the initial state."""
    _stop_openlist()

    deleted_bytes = 0
    deleted_items: list[str] = []
    errors: list[dict[str, str]] = []

    for target in [DATA_DIR, COVERS_DIR]:
        result = _remove_path(target)
        deleted_bytes += result["bytes"]
        if result["deleted"]:
            deleted_items.append(str(target))
        if result["error"]:
            errors.append({"path": str(target), "error": result["error"]})

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    _reset_config()
    db_service.init_db()

    return {
        "ok": not errors,
        "deleted": deleted_items,
        "deletedBytes": deleted_bytes,
        "errors": errors,
    }


def _reset_config() -> None:
    config = AppConfig()
    config._init_defaults()
    config.save_config()


def _stop_openlist() -> None:
    try:
        try:
            from backend.core.openlist_manager import openlist_manager
        except ImportError:
            from core.openlist_manager import openlist_manager

        openlist_manager.stop()
    except Exception as exc:
        logger.warning("Stop OpenList before reset failed: %s", exc)


def _remove_path(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not _is_allowed_delete_target(resolved):
        return {"deleted": False, "bytes": 0, "error": "delete target is outside managed backend data"}
    if not resolved.exists():
        return {"deleted": False, "bytes": 0, "error": ""}

    size = _path_size(resolved)
    try:
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
        return {"deleted": True, "bytes": size, "error": ""}
    except Exception as exc:
        logger.warning("Delete path failed: %s error=%s", resolved, exc)
        return {"deleted": False, "bytes": 0, "error": str(exc)}


def _is_allowed_delete_target(path: Path) -> bool:
    data_dir = DATA_DIR.resolve()
    covers_dir = COVERS_DIR.resolve()
    return path == data_dir or path == covers_dir or _is_within(path, data_dir)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size

    total = 0
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique
