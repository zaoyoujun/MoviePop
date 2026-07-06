"""
数据源管理服务
封装数据源的 CRUD、路径解析、类型标准化等业务逻辑
"""
import json
import logging
import random
import uuid
from typing import Any

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig
from . import db_service

logger = logging.getLogger(__name__)


# ==================== 加载/保存 ====================

def load_sources() -> list:
    """从 SQLite 数据库加载数据源列表"""
    sources = db_service.load_sources()
    changed = False
    for source in sources:
        if _normalize_openlist_source(source):
            changed = True
    if changed:
        db_service.save_sources(sources)
    return sources


def save_sources(sources: list) -> None:
    """保存数据源列表到 SQLite 数据库"""
    for source in sources:
        _normalize_openlist_source(source)
    db_service.save_sources(sources)


def _normalize_openlist_source(source: dict[str, Any]) -> bool:
    if source.get("type") != "openlist":
        return False

    mount_path = _normalize_mount_path(source.get("mount_path") or "")
    if mount_path and mount_path.lower() not in {"/", "/openlist"} and not mount_path.startswith("/__preview_"):
        return False

    inferred = _infer_openlist_mount_from_paths(source.get("selected_paths", []))
    if not inferred:
        inferred = _public_mount_for_driver(str(source.get("driver") or ""))
    if not inferred or inferred == mount_path:
        return False

    source["mount_path"] = inferred
    return True


def _normalize_mount_path(value: Any) -> str:
    mount_path = str(value or "").strip()
    if not mount_path:
        return ""
    if not mount_path.startswith("/"):
        mount_path = "/" + mount_path
    return mount_path.rstrip("/") or "/"


def _infer_openlist_mount_from_paths(paths: Any) -> str:
    if isinstance(paths, str):
        paths = [part.strip() for part in paths.split(",") if part.strip()]
    if not isinstance(paths, list):
        return ""
    for path in paths:
        normalized = "/" + str(path or "").strip("/")
        parts = [part for part in normalized.split("/") if part]
        if parts and not parts[0].startswith("__preview_"):
            return "/" + parts[0]
    return ""


def _public_mount_for_driver(driver: str) -> str:
    value = str(driver or "").strip().lower()
    aliases = {
        "quark": "/quark",
        "aliyundriveopen": "/aliyun",
        "aliyun": "/aliyun",
        "115 cloud": "/115",
        "115": "/115",
        "baidunetdisk": "/baidu",
        "baidu": "/baidu",
        "webdav": "/webdav",
    }
    return aliases.get(value, "")


def generate_id() -> str:
    """生成唯一 ID"""
    return uuid.uuid4().hex[:12]


# ==================== 类型标准化 ====================

_TYPE_LABEL_MAP = {
    "webdav": "WebDAV",
    "openlist": "OpenList",
    "local": "本地存储",
    "本地存储": "本地存储",
    "本地目录": "本地存储",
}


def normalize_type(raw: str) -> str:
    """将前端传来的类型标签标准化为内部标识"""
    t = (raw or "").strip()
    if t in ("webdav", "openlist", "local"):
        return t
    tl = t.lower()
    if "webdav" in tl:
        return "webdav"
    if "openlist" in tl or "open" in tl:
        return "openlist"
    if "本地" in t or tl == "local":
        return "local"
    return tl if t else ""


def get_type_label(source_type: str) -> str:
    """根据数据源类型返回显示标签"""
    labels = {
        "webdav": "WebDAV",
        "openlist": "OpenList",
        "local": "本地存储",
    }
    return labels.get(source_type, source_type)


# ==================== 安全输出 ====================

def safe_source(source: dict) -> dict:
    """返回不含密码等敏感信息的数据源，path 字段兼容前端解析"""
    raw_path = source.get("path", "")
    stype = source.get("type", "")

    sp = source.get("selected_paths", [])
    if stype in ("webdav", "openlist"):
        if sp and isinstance(sp, list) and len(sp) > 0:
            mount = ",".join(sp)
        else:
            mount = source.get("mount_path", "")
    else:
        mount = ""

    # OpenList 类型数据源需要额外返回 driver 和 addition 信息
    result = {
        "id": source.get("id", ""),
        "name": source.get("name", ""),
        "type": stype,
        "typeLabel": get_type_label(stype),
        "path": raw_path,
        "username": source.get("username", ""),
        "active": source.get("active", False),
        "tint": source.get("tint", ""),
        "driver": source.get("driver", ""),
        "cookie": "******" if stype == "openlist" and source.get("cookie") else source.get("cookie", ""),
        "mountPath": mount or source.get("mount_path", ""),
        "host": source.get("host", ""),
        "port": source.get("port", ""),
        "protocol": source.get("protocol", "http"),
        "selected_paths": source.get("selected_paths", []),
        "stats": source.get("stats", {
            "files": 0, "movies": 0, "series": 0, "anime": 0, "music": 0, "unmatched": 0,
        }),
        "createdAt": source.get("created_at", ""),
        "updatedAt": source.get("updated_at", ""),
        "scanError": source.get("scan_error", ""),
    }

    # OpenList 类型额外添加 addition 字段（不含敏感信息）
    if stype == "openlist":
        addition = source.get("addition", {})
        if isinstance(addition, dict):
            # 过滤敏感信息
            safe_addition = {}
            for key, value in addition.items():
                if key.lower() in ("password", "secret", "token", "cookie"):
                    safe_addition[key] = "******"
                else:
                    safe_addition[key] = value
            result["addition"] = safe_addition
        elif isinstance(addition, str):
            try:
                addition_dict = json.loads(addition)
                safe_addition = {}
                for key, value in addition_dict.items():
                    if key.lower() in ("password", "secret", "token", "cookie"):
                        safe_addition[key] = "******"
                    else:
                        safe_addition[key] = value
                result["addition"] = safe_addition
            except json.JSONDecodeError:
                result["addition"] = {}

    return result


# ==================== 随机主题色 ====================

def random_tint() -> str:
    """生成随机主题色"""
    tints = [
        "rgba(111, 110, 142, 0.62)",
        "rgba(95, 30, 30, 0.68)",
        "rgba(45, 83, 102, 0.66)",
        "rgba(91, 47, 116, 0.68)",
        "rgba(39, 98, 82, 0.66)",
        "rgba(101, 74, 38, 0.68)",
    ]
    return random.choice(tints)


# ==================== 启动清理 ====================

def cleanup_on_startup() -> int:
    """启动时清理无效和重复数据源，返回清理数量"""
    sources = load_sources()
    if not sources:
        return 0

    seen: dict[str, bool] = {}
    cleaned: list[dict] = []
    removed = 0

    for s in sources:
        stype = s.get("type", "")
        spath = s.get("path", "")

        # 移除路径无效的数据源
        if stype == "webdav" and spath in ("", "http://", "https://"):
            removed += 1
            logger.info(f"清理无效数据源: {s.get('name', '')}")
            continue

        # 去重
        key = stype + "|" + (s.get("host") or spath or "")
        if key not in seen:
            seen[key] = True
            cleaned.append(s)

    removed_dups = len(sources) - len(cleaned) - removed
    if removed > 0:
        logger.info(f"启动时清理 {removed} 个无效数据源")
    if removed_dups > 0:
        logger.info(f"启动时清理 {removed_dups} 个重复数据源")

    if len(cleaned) < len(sources):
        save_sources(cleaned)

    return removed + removed_dups
