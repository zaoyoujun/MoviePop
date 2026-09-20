"""G2：LLM 推荐精排服务（阶段四）。

规则召回 Top50 → LLM 结合用户画像重排并生成个性化中文理由。

产品约束（用户已确认）：
- 独立开关 LLM_RERANK_ENABLED（默认关），仅发现页手动按钮触发，冷启动不触发；
- 缓存 6~24h（digest：候选有序 id + 画像摘要 + 快照日期），refresh 可强刷；
- 超时 ~10s、JSON 失败、id 非法等任何异常一律静默回退规则排序，不阻塞页面；
- 不发送 overview（防 prompt 注入），只发结构化行：id|片名|年份|媒介|题材|评分|评分人数|热度排名。
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime

try:
    from backend.core import llm_client
    from backend.services import db_service, recommend_service
except ImportError:
    from core import llm_client
    from services import db_service, recommend_service

logger = logging.getLogger(__name__)

_RECALL_SIZE = 50        # 规则召回后交给 LLM 的候选数
_REASON_TOP_N = 15      # 仅前 N 名要求写理由
_CACHE_TTL_HOURS = 24   # 精排结果有效期
_LLM_TIMEOUT = 10       # 精排硬超时（秒），超时即回退
_MAX_TOKENS = 2048      # reasoning 模型耗尽时 llm_client 会自动放大重试一次

_SYSTEM_PROMPT = (
    "你是一个影视推荐排序引擎。根据用户观影偏好，对候选影视作品重新排序并给出简短中文推荐理由。\n"
    "规则：\n"
    "1. 只能使用给定候选中的 id，严禁发明 id 或引用候选之外的作品；\n"
    "2. 综合用户题材偏好、作品评分、评分人数、当前热度排名排序，用户偏好权重最高；\n"
    "3. 只为排在最前面的作品写理由，每条不超过35个汉字，要具体、个性化，不要空话套话；\n"
    "4. 其余作品 reason 输出空字符串；不要复述剧情，不要使用候选数据之外的信息；\n"
    '5. 只输出 JSON：{"ranking":[{"id":"P01","reason":"..."}]}，'
    'ranking 按推荐优先级降序，且必须包含全部候选 id。'
)


def _behavior_bucket(n: int) -> str:
    if n < 3:
        return "b0"
    if n < 6:
        return "b1"
    if n < 10:
        return "b2"
    return "b3"


def _build_digest(items: list[dict], profile: dict, snapshot_date: str) -> tuple[str, dict]:
    """构造稳定摘要 + digest。

    用分桶摘要而非原始浮点权重，避免 popularity/权重微小波动导致缓存永不命中。
    """
    genre_weights = profile.get("genre_weights", {}) or {}
    top_genres = [g for g, _ in sorted(genre_weights.items(),
                                       key=lambda x: x[1], reverse=True)[:3]]
    media = profile.get("media_type", {}) or {}
    mt_total = sum(media.values())
    tv_ratio = round(media.get("tv", 0.0) / mt_total, 1) if mt_total else 0.5
    summary = {
        "g": top_genres,
        "tv": tv_ratio,
        "b": _behavior_bucket(int(profile.get("behavior_count", 0))),
    }
    ids = [it["poolId"] for it in items]
    raw = json.dumps({"ids": ids, "p": summary, "d": snapshot_date or ""},
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest(), summary


def _read_cache_fresh(digest: str) -> dict | None:
    """读 digest 缓存并校验 TTL；过期/损坏返回 None。"""
    try:
        cached = db_service.get_llm_cache(llm_client.SCOPE_RECOMMEND_RERANK, digest)
    except Exception as exc:
        logger.debug("精排缓存读取失败: %s", exc)
        return None
    if not cached or not cached.get("response_text"):
        return None
    created = str(cached.get("created_at") or "")
    try:
        ts = datetime.fromisoformat(created)
        age_hours = (datetime.now() - ts).total_seconds() / 3600
        if age_hours > _CACHE_TTL_HOURS:
            return None
    except ValueError:
        return None
    return cached


def _build_user_prompt(items: list[dict], profile_summary: dict) -> str:
    """构造候选清单 prompt（无 overview，防注入；字段全部来自本地 DB）。"""
    prefs = "/".join(profile_summary.get("g") or []) or "暂无明显题材偏好"
    tv_ratio = profile_summary.get("tv", 0.5)
    media_desc = f"剧集约占 {tv_ratio:.0%}、电影约占 {1 - tv_ratio:.0%}"
    lines = [
        f"【用户偏好】偏好题材：{prefs}；{media_desc}；行为样本：{profile_summary.get('b')}",
        "【候选】格式 id|片名|年份|媒介|题材|评分(0-10)|评分人数|当前热度排名",
    ]
    for idx, it in enumerate(items):
        pid_num = idx + 1
        title = str(it.get("title") or it.get("originalTitle") or "").replace("\n", " ").replace("|", "丨")[:40]
        year = it.get("year") or ""
        media = "剧" if it.get("mediaType") == "tv" else "影"
        genres = "/".join((it.get("genres") or [])[:3]) or "未知"
        rating = round(float(it.get("voteAverage") or 0), 1)
        votes = int(it.get("voteCount") or 0)
        rank = it.get("hotRank") or pid_num
        lines.append(f"P{pid_num:02d}|{title}|{year}|{media}|{genres}|{rating}|{votes}|{rank}")
    lines.append(f'请输出 JSON，ranking 包含全部 {len(items)} 个 id（P01..P{len(items):02d}），'
                 f"前 {min(_REASON_TOP_N, len(items))} 名 reason 写理由，其余留空。")
    return "\n".join(lines)


def _apply_ranking(items: list[dict], parsed: object) -> tuple[list[dict], dict[str, str]]:
    """校验 LLM 输出：id 必须是输入子集、去重、缺失按规则序补尾。

    返回 (新顺序的 items, {poolId: reason})。
    """
    rule_order = [it["poolId"] for it in items]
    by_id = {it["poolId"]: it for it in items}
    reasons: dict[str, str] = {}
    ordered: list[str] = []
    seen: set[str] = set()

    ranking = parsed.get("ranking") if isinstance(parsed, dict) else None
    if not isinstance(ranking, list):
        raise ValueError("ranking 字段缺失或不是数组")

    for entry in ranking:
        if not isinstance(entry, dict):
            continue
        raw_id = str(entry.get("id") or "").strip()
        # 模型可能回填 tmdb:xxx 全名，做一次宽容映射
        pid = raw_id if raw_id in by_id else ""
        if not pid:
            for candidate_id in rule_order:
                if raw_id in (candidate_id, candidate_id.replace("tmdb:", "")):
                    pid = candidate_id
                    break
        if not pid or pid in seen:
            continue
        seen.add(pid)
        reason = str(entry.get("reason") or "").strip().replace("\n", " ")
        if reason:
            reasons[pid] = reason[:35]
        ordered.append(pid)

    # 缺失/被丢弃的 id 按规则序补尾，保证数量完整
    for pid in rule_order:
        if pid not in seen:
            ordered.append(pid)

    return [by_id[pid] for pid in ordered], reasons


def rerank_discover(limit: int = 12, refresh: bool = False) -> dict:
    """AI 精排发现推荐。任何失败都静默回退规则结果（reranked=False）。"""
    limit = max(1, min(50, limit))
    rule_result = recommend_service.rule_recall(_RECALL_SIZE)
    items_all: list[dict] = rule_result.get("items", [])

    def _fallback(fallback_reason: str, cached: bool = False) -> dict:
        out = dict(rule_result)
        out["items"] = items_all[:limit]
        out["reranked"] = False
        out["reasonSource"] = "rule"
        out["model"] = ""
        out["cached"] = cached
        out["fallbackReason"] = fallback_reason
        return out

    if not items_all:
        return _fallback("empty_candidates")
    # 冷启动不触发 LLM（用户已确认）
    if rule_result.get("coldStart"):
        return _fallback("cold_start")
    if not llm_client.feature_enabled("LLM_RERANK_ENABLED"):
        return _fallback("llm_disabled")

    profile = db_service.get_user_preference_profile()
    snapshot_date = str(rule_result.get("snapshotDate") or "")
    digest, profile_summary = _build_digest(items_all, profile, snapshot_date)

    cached = None if refresh else _read_cache_fresh(digest)
    model_name = ""
    parsed = None
    from_cache = False

    if cached is not None:
        model_name = str(cached.get("model") or "")
        parsed = llm_client._extract_json(cached["response_text"])
        from_cache = True
    else:
        user_prompt = _build_user_prompt(items_all, profile_summary)
        model_name = str(getattr(llm_client._load_config(), "LLM_MODEL", "") or "")
        raw = llm_client.chat_json(
            _SYSTEM_PROMPT,
            user_prompt,
            llm_client.SCOPE_RECOMMEND_RERANK,
            request_meta={"kind": "discover_rerank", "count": len(items_all),
                          "snapshot": snapshot_date},
            use_cache=False,          # 自行用 digest 管理缓存与 TTL
            max_tokens=_MAX_TOKENS,
            temperature=0.3,
            timeout=_LLM_TIMEOUT,
        )
        if raw is None:
            return _fallback("llm_timeout_or_error")
        parsed = raw

    try:
        ordered_items, reasons = _apply_ranking(items_all, parsed)
    except (ValueError, TypeError, AttributeError) as exc:
        logger.warning("精排结果校验失败，回退规则序: %s", exc)
        return _fallback("invalid_response", cached=from_cache)

    # 校验通过：新请求落 digest 缓存
    if not from_cache:
        try:
            db_service.set_llm_cache(
                llm_client.SCOPE_RECOMMEND_RERANK, digest,
                json.dumps(parsed, ensure_ascii=False),
                model=model_name,
                request_meta={"kind": "discover_rerank", "count": len(items_all),
                              "snapshot": snapshot_date},
            )
        except Exception as exc:
            logger.debug("精排缓存写入失败（不影响本次结果）: %s", exc)

    # 组装展示结果：按 LLM 序取前 limit；前 _REASON_TOP_N 可带长理由
    final_items: list[dict] = []
    for rank, it in enumerate(ordered_items[:limit]):
        item = dict(it)
        detail = reasons.get(item["poolId"], "")
        if rank < _REASON_TOP_N and detail:
            item["reasonDetail"] = detail
            item["reasonSource"] = "llm"
        else:
            item["reasonDetail"] = ""
            item["reasonSource"] = "rule"
        final_items.append(item)

    out = dict(rule_result)
    out["items"] = final_items
    out["reranked"] = True
    out["reasonSource"] = "llm"
    out["model"] = model_name
    out["cached"] = from_cache
    out["fallbackReason"] = ""
    return out
