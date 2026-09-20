"""G3：大模型观影自然语言报告。

将 analytics_service 聚合出的统计数字与观影人格喂给大模型，
生成个性化的月度/周期观影报告；LLM 不可用时回退到基于人格模板的本地文案。

隐私：只发送聚合数字、人格标签与 Top 片名（元数据），不发送路径、账号、Cookie。
缓存：报告 prompt 内含统计数字，数据变化后 hash 自然改变；同一份数据周期内只调用一次。
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

try:
    from backend.core import llm_client
    from backend.services import analytics_service, library_service as lib, db_service
except ImportError:
    from core import llm_client
    from services import analytics_service, library_service as lib, db_service

logger = logging.getLogger(__name__)

# 报告内列出的 Top 片单与题材数量（控制 prompt 体积与费用）
_TOP_TITLES_LIMIT = 5
_GENRE_LIMIT = 5

# 最后一份报告持久化到 app_state 的键前缀（按窗口天数分键，如 llm_report_last:30）
_LAST_REPORT_PREFIX = "llm_report_last:"

_SYSTEM_PROMPT = (
    "你是一位亲切、客观的个人观影数据分析师。用户会收到自己本地媒体库统计出的"
    "观影行为数据（观看时长、活跃天数、人格画像、题材分布等）。请据此写一份"
    "中文观影报告，要求：\n"
    "1. 使用 Markdown，包含「## 本期概览」「## 观影风格」「## 小建议」三个小节；\n"
    "2. 总字数 300~500 字，语气轻松自然，可以适度幽默，但不要夸张煽情；\n"
    "3. 所有结论必须基于给出的数据，不得编造片名、数字或事实；数据不足时直接说明；\n"
    "4. 建议要具体可行（例如结合高峰时段、题材集中度、完播率给出一两条）；\n"
    "5. 只输出报告正文，不要寒暄，不要输出 JSON 或代码块。"
)


def _build_metrics(days: int) -> dict[str, Any]:
    """从现有统计服务取数并裁剪为发送给模型的精简指标（聚合层，不含隐私字段）。"""
    movies = lib.load_library()
    events = db_service.load_behavior_events()
    now = datetime.now()
    activity = analytics_service.build_activity_summary(days, movies, events, now)
    personality = analytics_service.build_personality_profile(days, movies, events, now)

    top_titles = [
        {
            "title": str(item.get("title") or ""),
            "category": str(item.get("category") or ""),
            "watchMinutes": item.get("watchMinutes"),
            "playCount": item.get("playCount"),
        }
        for item in (activity.get("topTitles") or [])[:_TOP_TITLES_LIMIT]
        if item.get("title")
    ]
    genres = (personality.get("charts") or {}).get("genreDistribution") or []
    genre_distribution = [
        {"label": str(item.get("label") or ""), "percent": item.get("percent")}
        for item in genres[:_GENRE_LIMIT]
    ]

    return {
        "统计窗口天数": days,
        "观看时长小时": activity.get("watchHours"),
        "活跃天数": activity.get("activeDays"),
        "播放次数": activity.get("playCount"),
        "观看作品数": activity.get("uniqueTitles"),
        "活跃日日均分钟": activity.get("averageDailyMinutes"),
        "平均单次分钟": activity.get("averageSessionMinutes"),
        "当前连续活跃天数": activity.get("currentStreak"),
        "最长连续活跃天数": activity.get("longestStreak"),
        "高峰开始小时": activity.get("peakHour"),
        "常看作品Top": top_titles,
        "观影人格": {
            "类型": personality.get("name"),
            "标签": personality.get("tags"),
            "聚焦度": (personality.get("scores") or {}).get("focus"),
            "深耕度": (personality.get("scores") or {}).get("depth"),
            "规律度": (personality.get("scores") or {}).get("routine"),
            "置信度": personality.get("confidence"),
            "数据状态": personality.get("dataStatus"),
        },
        "题材分布Top": genre_distribution,
    }


def _fallback_report(metrics: dict[str, Any]) -> str:
    """LLM 不可用/失败时的本地模板报告，保证接口始终有内容。"""
    personality = metrics.get("观影人格") or {}
    name = personality.get("类型") or "观影者"
    tags = personality.get("标签") or []
    tag_text = "、".join(str(t) for t in tags[:3]) if tags else "风格待探索"
    lines = [
        "## 本期概览",
        f"近 {metrics.get('统计窗口天数')} 天共观看 {metrics.get('观看时长小时') or 0} 小时，"
        f"活跃 {metrics.get('活跃天数') or 0} 天，播放 {metrics.get('播放次数') or 0} 次，"
        f"覆盖 {metrics.get('观看作品数') or 0} 部作品。",
        "",
        "## 观影风格",
        f"你的观影人格为「{name}」（{tag_text}）。"
        f"聚焦度 {personality.get('聚焦度') if personality.get('聚焦度') is not None else '--'}、"
        f"深耕度 {personality.get('深耕度') if personality.get('深耕度') is not None else '--'}、"
        f"规律度 {personality.get('规律度') if personality.get('规律度') is not None else '--'}。",
    ]
    top = metrics.get("常看作品Top") or []
    if top:
        lines.append("本期最常看：" + "、".join(str(item.get("title")) for item in top[:3]) + "。")
    lines.extend(["", "## 小建议",
                  "配置 AI 大模型后可生成更细致的个性化解读；也可以多记录几天观影行为，让画像更准确。"])
    return "\n".join(lines)


def _metrics_hash(metrics: dict[str, Any]) -> str:
    """统计指标的稳定指纹：数字不变则 hash 不变，用于恢复报告时判断是否过期。"""
    payload = json.dumps(metrics, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _persist_last_report(days: int, payload: dict[str, Any]) -> None:
    """把最后一份非空报告写入 app_state（失败不影响生成流程）。"""
    try:
        db_service.set_app_state(
            f"{_LAST_REPORT_PREFIX}{days}", json.dumps(payload, ensure_ascii=False)
        )
    except Exception as exc:
        logger.debug("观影报告持久化失败（不影响本次结果）: %s", exc)


def get_last_report(days: int = 30) -> dict[str, Any]:
    """读取上次生成的报告（零 LLM 成本），并对比当前指标判断是否已过期。

    返回 {"found": bool, "stale": bool, "report": {...对齐 generate_viewing_report 结构}}。
    found=True 时 report 额外带 templateReport（本地模板实时重算，保证对比功能可用）。
    """
    days = max(7, min(int(days or 30), 365))
    empty = {"found": False, "stale": False, "report": {}}
    try:
        raw = db_service.get_app_state(f"{_LAST_REPORT_PREFIX}{days}")
    except Exception as exc:
        logger.debug("读取上次观影报告失败: %s", exc)
        return empty
    if not raw:
        return empty
    try:
        stored = json.loads(raw)
        report = dict(stored.get("report") or {})
        stored_hash = str(stored.get("metricsHash") or "")
    except (json.JSONDecodeError, TypeError):
        return empty
    if not report.get("report"):
        return empty

    stale = False
    template_report = ""
    try:
        metrics = _build_metrics(days)
        template_report = _fallback_report(metrics) if int(metrics.get("活跃天数") or 0) > 0 else ""
        if stored_hash:
            stale = stored_hash != _metrics_hash(metrics)
    except Exception as exc:
        logger.debug("计算报告过期状态失败（按未过期处理）: %s", exc)

    report["templateReport"] = template_report
    report["days"] = days
    report["stale"] = stale
    return {"found": True, "stale": stale, "report": report}


def generate_viewing_report(days: int = 30, *, force_refresh: bool = False,
                            include_template: bool = False) -> dict[str, Any]:
    """生成观影报告。

    返回 {"source": "llm"|"template"|"empty", "report": str, "model": str,
          "days": int, "generatedAt": iso, "message": str,
          "templateReport": str (仅当 source=llm 且 include_template=True)}
    - 数据为空：source=empty，提示先看几部片子；
    - AI 关闭/失败：source=template，本地模板兜底；
    - AI 成功：source=llm。force_refresh=True 时绕过缓存重新生成。
    - include_template=True 且 source=llm 时，附带 templateReport 供前端对比。
    """
    days = max(7, min(int(days or 30), 365))
    metrics = _build_metrics(days)

    if int(metrics.get("活跃天数") or 0) <= 0:
        return {
            "source": "empty",
            "report": "",
            "model": "",
            "days": days,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "message": "当前窗口内还没有观影记录，先看几部片子后再来生成报告吧。",
        }

    template_report = _fallback_report(metrics) if include_template else None
    metrics_hash = _metrics_hash(metrics)

    # 读取模型名，用于返回值中的 model 字段（让前端能展示是哪个模型生成的）
    try:
        from backend.config import AppConfig as _AC
        _cfg = _AC(); _cfg.load_config()
        current_model = str(getattr(_cfg, "LLM_MODEL", "") or "").strip()
    except Exception:
        try:
            from config import AppConfig as _AC
            _cfg = _AC(); _cfg.load_config()
            current_model = str(getattr(_cfg, "LLM_MODEL", "") or "").strip()
        except Exception:
            current_model = ""

    use_cache = not force_refresh
    report_text = None
    if llm_client.feature_enabled("LLM_REPORT_ENABLED"):
        import json
        user_prompt = (
            "以下是我的观影统计数据（JSON）：\n"
            + json.dumps(metrics, ensure_ascii=False, indent=2)
        )
        report_text = llm_client.chat_text(
            _SYSTEM_PROMPT,
            user_prompt,
            scope=llm_client.SCOPE_VIEWING_REPORT,
            request_meta={"days": days, "activeDays": metrics.get("活跃天数")},
            use_cache=use_cache,
            max_tokens=1536,
            temperature=0.6,
        )

    if report_text:
        result = {
            "source": "llm",
            "report": report_text,
            "model": current_model,
            "days": days,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "message": "AI 报告生成成功",
        }
        if include_template:
            result["templateReport"] = template_report
        _persist_last_report(days, {"report": result, "metricsHash": metrics_hash})
        return result

    ai_enabled = llm_client.is_ready() and llm_client.feature_enabled("LLM_REPORT_ENABLED")
    result = {
        "source": "template",
        "report": template_report or _fallback_report(metrics),
        "model": "",
        "days": days,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "message": "AI 暂不可用，已使用本地模板报告" if ai_enabled else "未开启 AI，当前为本地模板报告",
    }
    _persist_last_report(days, {"report": result, "metricsHash": metrics_hash})
    return result
