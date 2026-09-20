"""G1：大模型刮削智能识别。

规则解析器（filename_parser）对脏文件名仍有盲区：技术参数残留、季/部分信息混入片名、
中日英多语言原名归一化等。本模块在规则解析置信度低时，让大模型从文件名文本中
识别作品的规范名称，生成最适合 TMDB/豆瓣检索的搜索词。

硬性约束：
- 仅当 LLM 总开关就绪且 LLM_SCRAPE_ENABLED 开启时工作；
- 启发式门控：规则标题"干净"时不调用，节省费用；
- 只发送文件名（basename）与规则解析字段，绝不发送挂载根/绝对路径/账号信息；
- 任何失败返回 None，scan_service 继续使用规则标题，刮削链路零影响。
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

try:
    from backend.core import llm_client
except ImportError:
    from core import llm_client

logger = logging.getLogger(__name__)

# 规则标题中一旦残留这些技术噪声，说明规则清洗失败，值得让 LLM 再识别一次。
# 注意 _ . - 都是文件名常见分隔符且属于 \w，会让 \b 词边界失效，
# 因此检测前统一把分隔符归一化为空格（见 title_needs_llm）。
_NOISE_PATTERNS = [
    re.compile(r"(?:^|\s)(?:2160p|1080p|720p|480p|4k|8k)(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:x264|x265|h\.?264|h\.?265|hevc|avc|av1)(?:\s|$)",
               re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:web[- ]?dl|web[- ]?rip|bdrip|blu[- ]?ray|remux|hdtv|dvdrip)(?:\s|$)",
               re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:aac\d?(?:\.\d)?|dts(?:-hd)?|truehd|atmos|flac|ddp?\d\.\d)(?:\s|$)",
               re.IGNORECASE),
    # 季/集/Part 等本应被规则器剥离的结构残留在标题里
    re.compile(r"\bS\d{1,2}E\d{1,3}\b", re.IGNORECASE),
    re.compile(r"(?:^|\s)S\d{1,2}(?:\s|$)"),
    re.compile(r"\bSeason\s*\d+\b", re.IGNORECASE),
    re.compile(r"第\s*\d+\s*[集话話季]"),
    re.compile(r"(?:^|\s)(?:Part|P)\s*\d+(?:\s|$)", re.IGNORECASE),
    re.compile(r"[\[\(（【][^\]\)）】]{2,40}(?:studio|字幕组|压制|x265|hevc)[^\]\)）】]*[\]\)）】]",
               re.IGNORECASE),
]

# 规范搜索词允许的最大/最小长度
_MIN_QUERY_LEN = 2
_MAX_QUERY_LEN = 60
_MIN_CONFIDENCE = 0.6

_SYSTEM_PROMPT = (
    "你是影视文件元数据识别专家。一个本地媒体库程序已用正则规则从视频文件名中"
    "初步解析出片名，但规则结果可能残留分辨率/编码/压制组/季集等噪声，或没有把"
    "中文译名与外文原名对应起来。请根据给出的解析字段与文件名样本，判断该作品"
    "最规范、最适合在 TMDB 或豆瓣搜索到正确条目的名称。\n"
    "要求：\n"
    "1. 只输出 JSON，不要解释，不要 markdown 代码块；\n"
    "2. search_query 优先使用通用中文译名；若作品主要以原名传播（如多数日本动画），"
    "可使用最通行的原名；不要包含季数、部、Part、分辨率、编码、字幕组等任何附加信息；\n"
    "3. original_title 填写作品原文名（中文作品可留空字符串）；\n"
    "4. confidence 为 0~1 的置信度，信息严重不足时给低分。\n"
    '输出格式：{"search_query": string, "original_title": string, "confidence": number}'
)


def _rule_title(movie: dict[str, Any]) -> str:
    return str(
        movie.get("series_title")
        or movie.get("title")
        or movie.get("name")
        or movie.get("search_title")
        or ""
    ).strip()


def _file_samples(movie: dict[str, Any], limit: int = 3) -> list[str]:
    """从 movie 的 files 字段提取纯文件名（剥离目录，保护用户路径隐私）。"""
    files = movie.get("files")
    if not isinstance(files, list):
        return []
    names: list[str] = []
    for item in files:
        if isinstance(item, dict):
            raw = item.get("path") or item.get("name") or item.get("file") or ""
        else:
            raw = str(item or "")
        name = os.path.basename(str(raw).replace("\\", "/"))
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def title_needs_llm(title: str) -> bool:
    """启发式门控：判断规则标题是否可疑到值得调用 LLM。"""
    value = str(title or "").strip()
    if len(value) < _MIN_QUERY_LEN:
        return True
    # 文件名分隔符（_ . -）归一化为空格后再检测噪声，避免 \w 边界导致漏判
    normalized = re.sub(r"[_.\-]+", " ", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if any(pattern.search(normalized) for pattern in _NOISE_PATTERNS):
        return True
    # 标题中残留大量分隔符 token（典型未清洗文件名，如 "Show.Name.S02.1080p.x265"）
    if re.fullmatch(r"[A-Za-z0-9.\-_ ]{12,}", value) and value.count(".") >= 3:
        return True
    # 标题被技术符号切碎、空白过多
    if len(normalized.split()) > 7:
        return True
    return False


def _build_user_prompt(movie: dict[str, Any], title: str) -> str:
    payload = {
        "规则解析片名": title,
        "媒体分类": str(movie.get("category") or ""),
        "年份": int(movie.get("year_hint") or 0) or None,
        "季": int(movie.get("season") or 1),
        "季副标题": str(movie.get("season_title") or ""),
        "章节名": str(movie.get("chapter_name") or ""),
        "特殊类型": str(movie.get("special_type") or ""),
        "文件名字样本": _file_samples(movie),
    }
    return "请识别以下影片：\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _validate_query(value: Any) -> str:
    query = str(value or "").strip()
    # 禁止换行与异常控制字符；截断超长输出
    query = re.sub(r"\s+", " ", query).strip()
    if not (_MIN_QUERY_LEN <= len(query) <= _MAX_QUERY_LEN):
        return ""
    return query


def enhance_scrape_title(movie: dict[str, Any]) -> dict | None:
    """用 LLM 识别规范刮削标题。

    返回 {"title": str, "original_title": str, "confidence": float}；
    未启用、门控未命中、调用失败或结果不可信时返回 None，调用方使用规则标题。
    """
    if not llm_client.feature_enabled("LLM_SCRAPE_ENABLED"):
        return None

    title = _rule_title(movie)
    if not title_needs_llm(title):
        return None

    try:
        result = llm_client.chat_json(
            _SYSTEM_PROMPT,
            _build_user_prompt(movie, title),
            scope=llm_client.SCOPE_SCRAPE_QUERY,
            request_meta={"title": title[:60], "category": str(movie.get("category") or "")},
            max_tokens=768,
            temperature=0.1,
        )
    except Exception as exc:
        logger.debug("LLM 刮削识别异常，降级规则标题: %s", exc)
        return None

    if not isinstance(result, dict):
        return None

    query = _validate_query(result.get("search_query"))
    if not query:
        return None

    try:
        confidence = float(result.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < _MIN_CONFIDENCE:
        logger.info("LLM 识别置信度 %.2f 低于阈值，保留规则标题: %s", confidence, title)
        return None

    original = _validate_query(result.get("original_title")) or ""
    logger.info("LLM 刮削识别：%s -> %s（置信度 %.2f）", title, query, confidence)
    return {"title": query, "original_title": original, "confidence": confidence}
