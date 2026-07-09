"""
在线视频网站解析器
使用 yt-dlp 提取视频网站的视频资源信息
支持 1000+ 视频网站（Bilibili、YouTube、抖音、快手等）

提供网站浏览体验：
- 解析网站主页/频道，获取视频列表和播放列表
- 解析播放列表，获取其中的视频
- 解析单个视频，获取详细信息
"""
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests

logger = logging.getLogger(__name__)

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig


def _get_covers_dir():
    return AppConfig().COVERS_DIR


def _download_cover(thumbnail_url: str, video_id: str) -> str:
    if not thumbnail_url:
        return ""
    
    covers_dir = _get_covers_dir()
    covers_dir.mkdir(exist_ok=True)
    
    ext = ".jpg"
    parsed = urlparse(thumbnail_url)
    path_ext = os.path.splitext(parsed.path)[1]
    if path_ext.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = path_ext.lower()
    
    filename = f"online_{video_id}{ext}"
    local_path = str(covers_dir / filename)
    
    if os.path.exists(local_path):
        return f"/covers/{filename}"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": thumbnail_url
        }
        response = requests.get(thumbnail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        with open(local_path, "wb") as f:
            f.write(response.content)
        
        logger.info(f"Downloaded cover for {video_id}: {local_path}")
        return f"/covers/{filename}"
    except Exception as exc:
        logger.warning(f"Failed to download cover for {video_id}: {exc}")
        return ""


def _generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _format_duration(seconds: int) -> str:
    if not seconds:
        return ""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def browse_site(url: str) -> dict:
    """
    浏览视频网站，获取层级结构（播放列表、视频）
    优先使用 yt-dlp，失败时回退到网页解析器
    
    :param url: 视频网站URL
    :return: 包含层级信息的字典
    """
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "force_generic_extractor": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            },
            "playlist_items": "1-50",
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return _normalize_browse_result(info, url)
        except yt_dlp.utils.DownloadError as exc:
            logger.warning(f"yt-dlp failed, trying web parser: {exc}")
            return _fallback_to_web_parser(url)
        except Exception as exc:
            logger.warning(f"yt-dlp error, trying web parser: {exc}")
            return _fallback_to_web_parser(url)
    except ImportError:
        logger.warning("yt-dlp not installed, using web parser")
        return _fallback_to_web_parser(url)


def _fallback_to_web_parser(url: str) -> dict:
    """
    回退到网页解析器
    
    :param url: 视频网站URL
    :return: 包含层级信息的字典
    """
    try:
        from backend.core.web_parser import browse_web_site
    except ImportError:
        from core.web_parser import browse_web_site
    
    result = browse_web_site(url)
    if result.get("error"):
        return result
    return result


def extract_video_detail(url: str) -> dict:
    """
    提取单个视频的详细信息（用于播放）
    
    :param url: 视频URL
    :return: 包含视频详细信息的字典
    """
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed")
        return {"error": "yt-dlp 未安装，请先安装依赖"}
    
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "force_generic_extractor": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return _normalize_video_detail(info, url)
    except yt_dlp.utils.DownloadError as exc:
        logger.error(f"yt-dlp extract error: {exc}")
        return {"error": str(exc)}
    except Exception as exc:
        logger.error(f"yt-dlp extract error: {exc}", exc_info=True)
        return {"error": str(exc)}


def _normalize_browse_result(info: dict, original_url: str) -> dict:
    """标准化网站浏览结果"""
    if not isinstance(info, dict):
        return {"error": "无效的网站信息"}
    
    result = {
        "success": True,
        "originalUrl": original_url,
        "type": "unknown",
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "uploader": info.get("uploader", ""),
        "uploaderUrl": info.get("uploader_url", ""),
        "playlists": [],
        "videos": [],
        "subchannels": [],
    }
    
    if "entries" in info and info["entries"]:
        for entry in info["entries"]:
            if not isinstance(entry, dict):
                continue
            
            if entry.get("_type") == "playlist" or entry.get("entries"):
                playlist_info = _normalize_playlist(entry, original_url)
                if playlist_info:
                    result["playlists"].append(playlist_info)
            else:
                video_info = _normalize_browse_video(entry)
                if video_info:
                    result["videos"].append(video_info)
        
        if result["playlists"]:
            result["type"] = "channel"
        elif result["videos"]:
            if info.get("_type") == "playlist":
                result["type"] = "playlist"
            else:
                result["type"] = "video_list"
    else:
        video_info = _normalize_browse_video(info)
        if video_info:
            result["videos"].append(video_info)
            result["type"] = "single_video"
    
    return result


def _normalize_playlist(entry: dict, base_url: str) -> dict | None:
    """标准化播放列表信息"""
    playlist_url = entry.get("url") or entry.get("webpage_url") or ""
    if not playlist_url:
        return None
    
    return {
        "id": _generate_id(playlist_url),
        "url": playlist_url,
        "title": entry.get("title", "未命名播放列表"),
        "thumbnail": entry.get("thumbnail", ""),
        "videoCount": entry.get("playlist_count") or len(entry.get("entries", [])),
        "uploader": entry.get("uploader", ""),
        "type": "playlist",
    }


def _normalize_browse_video(entry: dict) -> dict | None:
    """标准化浏览模式下的视频信息"""
    video_url = entry.get("url") or entry.get("webpage_url")
    if not video_url:
        return None
    
    video_id = entry.get("id") or _generate_id(video_url)
    thumbnail = entry.get("thumbnail", "")
    cover_url = _download_cover(thumbnail, video_id)
    
    return {
        "id": video_id,
        "url": video_url,
        "title": entry.get("title", "未命名视频"),
        "description": entry.get("description", ""),
        "coverUrl": cover_url,
        "backdropUrl": cover_url,
        "thumbnail": thumbnail,
        "duration": entry.get("duration", 0),
        "durationText": _format_duration(entry.get("duration", 0)),
        "year": int(entry.get("upload_date", "")[:4]) if entry.get("upload_date") else None,
        "uploader": entry.get("uploader", ""),
        "viewCount": entry.get("view_count", 0),
        "likeCount": entry.get("like_count", 0),
        "type": "video",
    }


def _normalize_video_detail(info: dict, original_url: str) -> dict:
    """标准化视频详细信息（用于播放）"""
    if not isinstance(info, dict):
        return {"error": "无效的视频信息"}
    
    video_id = info.get("id") or _generate_id(original_url)
    thumbnail = info.get("thumbnail", "")
    cover_url = _download_cover(thumbnail, video_id)
    
    return {
        "success": True,
        "id": video_id,
        "url": info.get("webpage_url", original_url),
        "title": info.get("title", "未命名视频"),
        "description": info.get("description", ""),
        "coverUrl": cover_url,
        "backdropUrl": cover_url,
        "thumbnail": thumbnail,
        "duration": info.get("duration", 0),
        "durationText": _format_duration(info.get("duration", 0)),
        "year": int(info.get("upload_date", "")[:4]) if info.get("upload_date") else None,
        "uploader": info.get("uploader", ""),
        "uploaderUrl": info.get("uploader_url", ""),
        "viewCount": info.get("view_count", 0),
        "likeCount": info.get("like_count", 0),
        "originalUrl": original_url,
    }


def generate_online_movie_entry(video_info: dict) -> dict:
    """将视频信息转换为电影库条目格式"""
    now = datetime.now().isoformat()
    
    return {
        "id": video_info.get("id", ""),
        "name": video_info.get("title", ""),
        "title": video_info.get("title", ""),
        "category": "online",
        "year": video_info.get("year", 0),
        "intro": video_info.get("description", ""),
        "cover_url": video_info.get("coverUrl", ""),
        "backdrop_url": video_info.get("backdropUrl", ""),
        "file_path": video_info.get("url", ""),
        "duration": video_info.get("durationText", ""),
        "source_type": "online",
        "source_name": "在线视频",
        "source_id": "online",
        "is_favorite": False,
        "metadata_locked": False,
        "updated_at": now,
        "playback": {},
        "episodes": [],
        "tags": ["在线"],
        "rating": 0,
    }