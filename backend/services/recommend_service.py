"""发现推荐服务（阶段四升级）。

从虚拟片库（metadata_pool）+ 热度时间序列（hotness_series）中推荐作品，
候选 = 最新热度快照 Top ∪ 片库 popularity Top（去重，覆盖全量约 1 万条目）。

四路信号（均归一到 [0,1]，缺信号中性 0.5）：
  s1 题材匹配：行为强度加权的用户题材画像 vs 候选题材（热启动主导）
  s2 外部热度：log1p(popularity) + log1p(vote_count)
  s3 热度趋势：跨自然日快照的 vote_count 增长率（≥20h 间隔门控，否则中性且权重置 0）
  s4 分类质量：贝叶斯加权评分 + 媒介类型亲和 + 动漫推断（动画∩JP）

权重：
  热启动  w1=0.30 w2=0.30 w3=0.15 w4=0.25
  冷启动  w1=0.00 w2=0.60 w3=0.10 w4=0.30
连续混合：score = c·warm + (1-c)·cold，c = min(1, behavior_count / 10)。
"""
from __future__ import annotations

import math
from typing import Any

try:
    from backend.services import db_service
except ImportError:
    from services import db_service

# 行为数达到该值视为完全热启动（混合系数 c=1）
_WARM_FULL_BEHAVIORS = 10
# 前端冷启动语义标记（c 低于该值时报告 coldStart=true）
_COLD_FLAG_RATIO = 0.3
# 规则召回候选规模（UNION 后），G2 精排取其中 Top50
_CANDIDATE_LIMIT = 500
_HOTNESS_CANDIDATE_LIMIT = 300
# 贝叶斯评分先验：低于该投票数的评分向全局均值收缩
_BAYES_M = 200.0
_BAYES_C = 7.0
# 权重（热/冷）
_WARM_W = (0.30, 0.30, 0.15, 0.25)  # s1 题材 / s2 热度 / s3 趋势 / s4 质量分类
_COLD_W = (0.00, 0.60, 0.10, 0.30)


def _normalize(values: list[float]) -> list[float]:
    """min-max 归一化到 [0,1]；全相等时返回全 0.5（缺信号中性）。"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    span = hi - lo
    return [(v - lo) / span for v in values]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_name_list(raw: Any) -> list[str]:
    """解析 JSON 数组字符串字段（genres / origin_country）。"""
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = db_service._safe_json(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    return [x.strip() for x in text.split(",") if x.strip()]


def _is_anime(genres: list[str], countries: list[str]) -> bool:
    """动漫 = 题材含"动画" 且 原产国含日本（避免把欧美动画长片误判为动漫）。"""
    return "动画" in genres and any(c.upper() in ("JP", "JPN", "日本") for c in countries)


def _bayes_rating(rating: float, vote_count: float) -> float:
    """IMDb 式贝叶斯加权评分（0~10）：投票越少越向先验均值收缩。"""
    v = max(0.0, vote_count)
    r = max(0.0, min(10.0, rating))
    return (v / (v + _BAYES_M)) * r + (_BAYES_M / (v + _BAYES_M)) * _BAYES_C


def _gather_candidates() -> list[dict]:
    """热度快照 Top ∪ 片库 popularity Top，按 pool_id 去重（快照行优先，值更新）。"""
    merged: dict[str, dict] = {}
    # 先放片库 Top（底）
    for c in db_service.get_top_pool_by_popularity(_CANDIDATE_LIMIT):
        pid = c.get("pool_id")
        if pid:
            merged[pid] = c
    # 快照 Top 覆盖（更新的热度值）
    for c in db_service.get_top_hotness_by_popularity(_HOTNESS_CANDIDATE_LIMIT):
        pid = c.get("pool_id")
        if pid:
            merged[pid] = c
    candidates = list(merged.values())
    candidates.sort(key=lambda x: _safe_float(x.get("popularity")), reverse=True)
    return candidates[:_CANDIDATE_LIMIT]


def _rule_recall(profile: dict, candidates: list[dict]) -> tuple[list[dict], dict]:
    """规则召回打分，返回 (有序 item 列表, 上下文元信息)。"""
    behavior_count = profile.get("behavior_count", 0)
    mix = min(1.0, behavior_count / float(_WARM_FULL_BEHAVIORS))
    cold_flag = mix < _COLD_FLAG_RATIO
    owned_ids = profile.get("owned_external_ids", set())

    # 题材画像归一
    genre_weights: dict[str, float] = profile.get("genre_weights", {}) or {}
    genre_total = sum(genre_weights.values())
    genre_pref = {g: w / genre_total for g, w in genre_weights.items()} if genre_total > 0 else {}

    # 媒介画像归一（行为强度加权）
    media_pref = profile.get("media_type", {}) or {}
    mt_total = sum(media_pref.values())
    mt_ratio = {
        "movie": (media_pref.get("movie", 0.0) / mt_total) if mt_total else 0.5,
        "tv": (media_pref.get("tv", 0.0) / mt_total) if mt_total else 0.5,
    }
    anime_pref = genre_pref.get("动画", 0.0)

    # 候选集内热度归一
    pop_norm = _normalize([math.log1p(_safe_float(c.get("popularity"))) for c in candidates])
    vote_norm = _normalize([math.log1p(_safe_float(c.get("vote_count"))) for c in candidates])

    # 趋势（批量）
    trends = db_service.get_hotness_trends([c.get("pool_id") for c in candidates if c.get("pool_id")])
    trend_available_any = any(t.get("available") for t in trends.values())
    snapshot_date = db_service.get_latest_snapshot_date()

    # 整体无跨天趋势时，w3 权重置 0 并按比例重归一（禁止用假趋势影响排序）
    def _renorm_drop_trend(w: tuple[float, ...]) -> tuple[float, ...]:
        kept = [x if i != 2 else 0.0 for i, x in enumerate(w)]
        total = sum(kept)
        return tuple(x / total for x in kept) if total > 0 else tuple(kept)

    warm_w = _WARM_W if trend_available_any else _renorm_drop_trend(_WARM_W)
    cold_w = _COLD_W if trend_available_any else _renorm_drop_trend(_COLD_W)

    n = len(candidates)
    scored: list[dict] = []
    for idx, c in enumerate(candidates):
        media_type = (c.get("media_type") or "").lower()
        genres = _parse_name_list(c.get("genres"))
        countries = _parse_name_list(c.get("origin_country"))
        # Bangumi 源条目 media_type='anime' 直接判定；TMDB 源走题材+国家推断
        anime = media_type == "anime" or _is_anime(genres, countries)
        external_id = str(c.get("external_id") or "")
        owned = external_id in owned_ids

        # s1 题材匹配（候选命中的画像题材权重求和，封顶 1）
        s1 = min(1.0, sum(genre_pref.get(g, 0.0) for g in genres)) if genre_pref else 0.5

        # s2 外部热度
        s2 = 0.5 * pop_norm[idx] + 0.5 * vote_norm[idx]

        # s3 趋势：整体无跨天数据时给中性（且最终权重置 0）
        t = trends.get(c.get("pool_id") or "", {})
        if t.get("available"):
            vt = 0.5 + 0.5 * math.tanh(2.0 * _safe_float(t.get("voteGrowth")))
            pt = 0.5 + 0.5 * math.tanh(2.0 * _safe_float(t.get("popChange")))
            s3 = 0.7 * vt + 0.3 * pt
            vote_growth = _safe_float(t.get("voteGrowth"))
        else:
            s3 = 0.5
            vote_growth = 0.0

        # s4 分类质量：贝叶斯评分 + 媒介/动漫亲和
        bayes = _bayes_rating(_safe_float(c.get("vote_average"), _BAYES_C),
                              _safe_float(c.get("vote_count")))
        quality = bayes / 10.0
        affinity = mt_ratio.get(media_type, 0.5)
        if anime:
            affinity = max(affinity, anime_pref)
        s4_cold = quality
        s4_warm = 0.65 * quality + 0.35 * affinity

        warm_score = (warm_w[0] * s1 + warm_w[1] * s2 + warm_w[2] * s3
                      + warm_w[3] * s4_warm)
        cold_score = cold_w[1] * s2 + cold_w[2] * s3 + cold_w[3] * s4_cold
        score = mix * warm_score + (1.0 - mix) * cold_score

        reason, matched_genre = _build_reason(
            cold_flag=cold_flag,
            hot_rank=idx + 1,
            total=n,
            bayes=bayes,
            s1=s1,
            genres=genres,
            genre_pref=genre_pref,
            trend_available=bool(t.get("available")),
            vote_growth=vote_growth,
            owned=owned,
        )

        scored.append({
            "poolId": c.get("pool_id") or "",
            "source": c.get("source") or "tmdb",
            "externalId": external_id,
            "title": c.get("title") or "",
            "originalTitle": c.get("original_title") or "",
            "mediaType": media_type,
            "posterPath": c.get("poster_path") or "",
            "backdropPath": c.get("backdrop_path") or "",
            "year": c.get("year"),
            "voteAverage": c.get("vote_average"),
            "voteCount": c.get("vote_count"),
            "popularity": c.get("popularity"),
            "genres": genres,
            "isAnime": anime,
            "hotRank": idx + 1,
            "signals": {"s1": round(s1, 4), "s2": round(s2, 4),
                        "s3": round(s3, 4), "s4": round(s4_warm, 4),
                        "quality": round(quality, 4), "affinity": round(affinity, 4),
                        "trend": round(vote_growth, 4)},
            "score": round(score, 4),
            "reason": reason,
            "reasonDetail": "",      # G2 LLM 长理由（规则路径留空）
            "reasonSource": "rule",
            "matchedGenre": matched_genre,
            "owned": owned,
        })

    # 已拥有轻微降权（让用户更多发现新内容），但不完全排除
    scored.sort(key=lambda x: x["score"] - (0.05 if x["owned"] else 0.0), reverse=True)

    context = {
        "coldStart": cold_flag,
        "behaviorCount": behavior_count,
        "mixRatio": round(mix, 3),
        "trendAvailable": trend_available_any,
        "snapshotDate": snapshot_date,
        "candidateCount": n,
    }
    return scored, context


def rule_recall(limit: int = 50) -> dict:
    """规则召回（G2 精排的底座）：返回完整上下文 + 规则序 Top N，供 LLM 重排。"""
    profile = db_service.get_user_preference_profile()
    candidates = _gather_candidates()
    if not candidates:
        return {
            "coldStart": profile.get("behavior_count", 0) < int(_WARM_FULL_BEHAVIORS * _COLD_FLAG_RATIO),
            "behaviorCount": profile.get("behavior_count", 0),
            "mixRatio": 0.0,
            "trendAvailable": False,
            "snapshotDate": "",
            "candidateCount": 0,
            "items": [],
        }
    items, context = _rule_recall(profile, candidates)
    context["items"] = items[:limit]
    return context


def discover_recommendations(limit: int = 12) -> dict:
    """生成发现推荐（规则路径）。返回 items + 画像/数据上下文。"""
    limit = max(1, min(50, limit))
    return rule_recall(limit)


def _build_reason(cold_flag: bool, hot_rank: int, total: int, bayes: float,
                  s1: float, genres: list[str], genre_pref: dict[str, float],
                  trend_available: bool, vote_growth: float, owned: bool) -> tuple[str, str]:
    """生成规则短标签（优先级从高到低），返回 (标签, 命中的题材名)。

    注意：只有 trend_available 为真时才允许使用"上升/环比"类趋势措辞，
    快照不足跨天时禁止假造趋势。
    """
    if owned:
        return "片库已有", ""
    if trend_available and vote_growth >= 0.15:
        return "近期热度上升", ""
    # 热启动下题材强匹配：取候选题材中画像权重最高的
    matched = ""
    if not cold_flag and genre_pref:
        hit = [(g, genre_pref.get(g, 0.0)) for g in genres if g in genre_pref]
        if hit:
            hit.sort(key=lambda x: x[1], reverse=True)
            matched = hit[0][0]
        if s1 >= 0.45 and matched:
            return f"你常看{matched}", matched
    if bayes >= 8.0:
        return "高分佳作", ""
    if total > 0 and hot_rank <= max(10, int(total * 0.1)):
        return "正在热门", ""
    if cold_flag:
        return "热门发现", ""
    return "为你发现", matched
