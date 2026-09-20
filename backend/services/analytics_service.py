"""Viewing-personality analytics and behavior event collection."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

try:
    from backend.services import db_service
    from backend.services import library_service as lib
    from backend.core import genre_taxonomy
except ImportError:
    from services import db_service
    from services import library_service as lib
    from core import genre_taxonomy


EVENT_TYPES = {
    "play_start",
    "play_heartbeat",
    "play_end",
    "pause",
    "resume",
    "seek_forward",
    "seek_backward",
    "rate_change",
    "detail_view",
    "favorite_add",
    "favorite_remove",
    "search",
    "recommend_click",
    "history_click",
    "home_click",
}

PERSONALITIES = {
    "FDR": ("影院守序者", ["仪式感信徒", "垂直品类死忠", "秩序感达人"], "你更像把观影当成一场稳定的精神仪式，偏爱熟悉题材，并倾向完整认真地看完作品。"),
    "FDC": ("题材考据员", ["圈层深度爱好者", "细节控", "为爱发电型"], "你会在少数热爱的题材里挖得很深，回看、补设定和反复确认细节，是典型的深耕型观众。"),
    "FWR": ("日程品鉴师", ["全能资深影迷", "生活规划家", "品质优先派"], "你的观看节奏稳定，题材覆盖也更宽，观影像一种有计划的审美充电。"),
    "FWC": ("漫游观影家", ["沉浸式体验派", "随遇而安", "杂食探索者"], "你愿意探索不同题材，选择随性但进入剧情后投入度不错，享受未知带来的惊喜。"),
    "SDR": ("定点速食者", ["高效解压党", "下饭刚需", "节奏大师"], "你常在固定场景里高效观看熟悉内容，偏短、偏稳定，倍速和跳转会成为节奏工具。"),
    "SDC": ("摸鱼常驻员", ["电子榨菜专业户", "熟剧复读机", "陪伴感选手"], "你更重视陪伴感和低压力，常回到熟悉作品，暂停、回拉和零散观看会更多。"),
    "SWR": ("榜单打卡机", ["观影打卡达人", "热门猎手", "谈资储备者"], "你倾向快速覆盖更多作品和热门内容，广度优先，观看行为带有明确的打卡感。"),
    "SWC": ("随机冲浪者", ["无聊消解者", "注意力漂流派", "盲盒选择手"], "你的观看更随机，切换和试探较多，观影常用于即时消遣而不是完成计划。"),
    "XXX": ("未知因素", ["数据采集中", "画像未稳定"], "当前观看数据还不够稳定，继续播放几部作品后会生成更可信的观影人格。"),
}

PERSONALITY_LONG_COPY = {
    "FDR": {
        "description": "你把观影当作一场郑重的精神仪式，生活作息规律，审美口味稳定。你通常只在自己认可的题材里深耕，不轻易尝试陌生领域，对作品质量有很高要求。你反感被打断，也不太喜欢用倍速和频繁快进破坏观看节奏。在你看来，一部作品就应该从头到尾完整欣赏，片头、片尾、配乐、转场和留白都是作品表达的一部分。对你而言，固定时段的观影不是消遣，而是生活里雷打不动的精神自留地。",
        "typicalDay": "你会提前备好零食和饮品，准时坐到屏幕前；全程不开倍速，不跳剧情，看完正片后甚至会把片尾曲听完再退出。你只追熟悉的导演、系列或题材，很少跳坑，也很少把新类型当作随机尝试。",
    },
    "FDC": {
        "description": "你是单一领域里的内容活百科，观影完全由兴趣驱动。你没有特别固定的时间表，但一旦遇到热爱的题材，就会挖得很深：反复回看细节，寻找彩蛋，梳理世界观，甚至主动补幕后资料来完善认知。你可以为了补完一个系列熬通宵，也可以半个月不打开播放器。你的兴趣不是广撒网，而是把少数真正喜欢的内容看透、吃透、拆透。",
        "typicalDay": "你会突然想起某个名场面，就翻出来反复拖进度条品鉴；也会为了看懂一部新作，提前补完前作设定。同一部作品刷五六遍也不奇怪，每次都能发现新细节。除了本命题材，其他内容往往很难真正吸引你。",
    },
    "FWR": {
        "description": "你把观影纳入规律生活日程，当作固定的审美充电环节。你既不局限于单一题材，也不会放低观看标准；从文艺片到商业爽片，从老经典到新上映，你都愿意认真对待。你有自己的片单和观影节奏，追求质量与数量的平衡，是标准的正经影迷。观影对你来说既是放松，也是自我拓展的方式。",
        "typicalDay": "你会每天预留固定的观影时间，按片单一部部推进。多数作品都会完整看完，也会形成自己的评分和判断。你愿意尝试冷门佳作，也不排斥热门爆款，涉猎广泛但审美在线。",
    },
    "FWC": {
        "description": "你是观影世界里的漫游旅行者，没有固定片单，也没有固定时间表，更多是凭当下心情选片。你不太挑题材，什么类型都愿意点开试试，但只要进入剧情，就会沉下心认真看完。你享受未知带来的惊喜，观影的乐趣在于随手打开一部作品，像开启一场随机的精神冒险。",
        "typicalDay": "你可能晚上没事就翻片库，看到封面或简介感兴趣就点开；也可能凌晨突发奇想刷完整部文艺片，或者连续几天完全不想看。你从不严格执行观影计划，主打兴之所至。",
    },
    "SDR": {
        "description": "你有精准固定的碎片观影场景，比如吃饭、睡前或通勤。你的核心诉求是高效获得快乐，只看熟悉的垂直题材，不轻易跳新坑。你习惯用倍速、快进或跳过冗余片段，精准抓取核心剧情。对你来说，观影是固定时段里的标准化精神快餐，稳定、高效、不费脑，刚好填满碎片时间。",
        "typicalDay": "吃饭时你会准时点开常追剧集，可能自动开 1.25x 或 1.5x，跳过片头片尾。看完刚好放下碗筷，节奏分秒不差。你总在追那几个安心类型，效率和熟悉感都很重要。",
    },
    "SDC": {
        "description": "你的观影大多发生在工作、学习或休息间隙，核心需求是陪伴感和无压力解压。你经常回到已经看过的老片老剧，不需要费脑追剧情，随便点开哪一段都能进入状态。你可能频繁暂停、随时退出，也会拖动进度条寻找名场面。内容对你来说更像背景陪伴，情绪价值才是第一位。",
        "typicalDay": "写作业、加班或摸鱼时，你会把熟悉的老剧当背景音；偶尔抬头看两眼经典片段，看完继续忙。你总在循环那几部作品，主打听个响就安心，完播并不是最重要。",
    },
    "SWR": {
        "description": "你有明确的刷片目标，习惯跟着榜单、年度清单和热门推荐选片。什么火就看什么，追求观影数量和知识面覆盖。你习惯用倍速、快进快速过片，重点是看过、标记、积累片单和储备谈资。对你来说，观影更像一种内容收集，广度永远优先于深度。",
        "typicalDay": "你会照着 TOP 榜单、年度热门或推荐页列片单，每天固定时间推进。拖沓片段会直接快进，看完立刻标记已看，然后赶下一部。各种题材都会沾一点，热门内容基本都能聊上两句。",
    },
    "SWC": {
        "description": "你打开播放器时往往没有明确目标，只是单纯想打发时间。你会漫无目的地翻页、滑动，点开一部看几分钟觉得没意思就切走，一晚上可能换好几部作品。你会拉满倍速、频繁跳片段，什么题材都碰一点，但很少完整看完。观影对你来说是消解无聊的工具，没有规划，也没有执念，随波逐流就好。",
        "typicalDay": "你可能躺着无聊打开应用，翻来翻去不知道看什么；点开一部看五分钟觉得不对味就退出，再刷下一个。一个晚上过去换了七八部，一部也没完整看完，主打消磨时间。",
    },
    "XXX": {
        "description": "当前观看样本还不足以稳定判断你的观影人格。系统已经开始记录你的观看时长、完播率、题材偏好、时间节律和播放操作习惯；等有效观看数据继续积累后，会生成更接近真实习惯的人格侧写。",
        "typicalDay": "继续正常观看几部作品即可。你不需要刻意配合算法，真实使用行为越自然，最终画像越准确。",
    },
}


def record_event(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = _normalize_event_type(payload.get("event_type") or payload.get("eventType"))
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event_type: {event_type or payload.get('eventType') or ''}")

    event = {
        "event_type": event_type,
        "movie_id": str(payload.get("movie_id") or payload.get("movieId") or "").strip(),
        "episode_id": str(payload.get("episode_id") or payload.get("episodeId") or "").strip(),
        "source_page": str(payload.get("source_page") or payload.get("sourcePage") or "").strip(),
        "position": _safe_float(payload.get("position") or payload.get("currentTime")),
        "duration": _safe_float(payload.get("duration")),
        "playback_rate": _safe_float(payload.get("playback_rate") or payload.get("playbackRate"), 1.0),
        "delta_seconds": _safe_float(payload.get("delta_seconds") or payload.get("deltaSeconds") or payload.get("watchSecondsDelta")),
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        "created_at": str(payload.get("created_at") or payload.get("createdAt") or datetime.now().isoformat(timespec="seconds")),
    }
    event_id = db_service.save_behavior_event(event)
    return {"id": event_id, **event}


def record_play_start(movie_id: str, episode_id: str = "", source_page: str = "", position: float = 0, duration: float = 0) -> None:
    if movie_id:
        record_event({
            "event_type": "play_start",
            "movie_id": movie_id,
            "episode_id": episode_id,
            "source_page": source_page,
            "position": position,
            "duration": duration,
        })


def record_play_heartbeat(movie_id: str, episode_id: str = "", position: float = 0, duration: float = 0, delta_seconds: float = 0, playback_rate: float = 1) -> None:
    if movie_id:
        record_event({
            "event_type": "play_heartbeat",
            "movie_id": movie_id,
            "episode_id": episode_id,
            "position": position,
            "duration": duration,
            "delta_seconds": _watch_delta_seconds(delta_seconds),
            "playback_rate": playback_rate,
        })


def build_activity_summary(
    days: int = 90,
    movies: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a date-bounded viewing activity summary from real playback data.

    Library playback is a current-state snapshot, while behavior events retain
    the time dimension that a statistics dashboard needs. Saved playback is a
    lifetime snapshot, so it is deliberately not repurposed as a date-bounded
    activity trend when events are unavailable.
    """
    days = max(7, min(int(days or 90), 365))
    now = now or datetime.now()
    movies = list(movies) if movies is not None else lib.load_library()
    today = now.date()
    start_date = today - timedelta(days=days - 1)
    start_at = datetime.combine(start_date, datetime.min.time())
    events = _events_in_window(events if events is not None else db_service.load_behavior_events(), start_at, now)
    unique_play_start_ids = _deduplicated_play_start_ids(events)
    movie_index = {str(movie.get("id") or ""): movie for movie in movies if movie.get("id")}

    daily_seconds: Counter[str] = Counter()
    daily_plays: Counter[str] = Counter()
    hour_counter: Counter[int] = Counter()
    weekday_counter: Counter[int] = Counter()
    movie_seconds: Counter[str] = Counter()
    movie_plays: Counter[str] = Counter()
    active_dates: set[str] = set()
    activity_event_count = 0

    for event in events:
        event_type = str(event.get("event_type") or "").strip().lower()
        if event_type not in {"play_start", "play_heartbeat", "play_end"}:
            continue
        played_at = _parse_time(event.get("created_at"))
        if not played_at:
            continue
        if event_type == "play_start" and id(event) not in unique_play_start_ids:
            continue

        activity_event_count += 1
        date_key = played_at.date().isoformat()
        active_dates.add(date_key)
        movie_id = str(event.get("movie_id") or "").strip()
        delta_seconds = _watch_delta_seconds(event.get("delta_seconds"))

        if event_type == "play_start":
            daily_plays[date_key] += 1
            hour_counter[played_at.hour] += 1
            weekday_counter[played_at.weekday()] += 1
            if movie_id:
                movie_plays[movie_id] += 1

        if delta_seconds:
            daily_seconds[date_key] += delta_seconds
            if movie_id:
                movie_seconds[movie_id] += delta_seconds

    watch_seconds = int(sum(daily_seconds.values()))
    top_movie_ids = sorted(
        set(movie_seconds) | set(movie_plays),
        key=lambda movie_id: (movie_seconds.get(movie_id, 0), movie_plays.get(movie_id, 0), movie_id),
        reverse=True,
    )[:6]
    top_titles = []
    for movie_id in top_movie_ids:
        movie = movie_index.get(movie_id) or {}
        top_titles.append({
            "id": movie_id,
            "available": bool(movie),
            "title": str(movie.get("metadata_title") or movie.get("title") or movie_id),
            "category": _category(movie) if movie else "",
            "coverUrl": str(movie.get("cover_url") or movie.get("backdrop_url") or ""),
            "watchSeconds": int(movie_seconds.get(movie_id, 0)),
            "watchMinutes": round(movie_seconds.get(movie_id, 0) / 60, 1),
            "playCount": int(movie_plays.get(movie_id, 0)),
        })

    trend = []
    for offset in range(days):
        current_day = start_date + timedelta(days=offset)
        date_key = current_day.isoformat()
        seconds = daily_seconds.get(date_key, 0)
        trend.append({
            "date": date_key,
            "label": f"{current_day.month}/{current_day.day}",
            "value": round(seconds / 60, 1),
            "minutes": round(seconds / 60, 1),
            "playCount": int(daily_plays.get(date_key, 0)),
        })

    peak_hour = max(hour_counter, key=hour_counter.get) if hour_counter else None
    current_streak, longest_streak = _streak_summary(active_dates, today)
    active_days = len(active_dates)
    play_count = int(sum(daily_plays.values()))
    unique_titles = len({movie_id for movie_id in set(movie_seconds) | set(movie_plays) if movie_id})

    return {
        "days": days,
        "dataSource": "events" if activity_event_count else "none",
        "watchSeconds": watch_seconds,
        "watchHours": round(watch_seconds / 3600, 1),
        "activeDays": active_days,
        "playCount": play_count,
        "uniqueTitles": unique_titles,
        "averageDailyMinutes": round(watch_seconds / max(1, active_days) / 60, 1) if active_days else 0,
        "averageSessionMinutes": round(watch_seconds / play_count / 60, 1) if play_count else 0,
        "currentStreak": current_streak,
        "longestStreak": longest_streak,
        "peakHour": peak_hour,
        "dailyTrend": trend,
        "hourDistribution": [
            {"hour": hour, "label": f"{hour:02d}:00", "value": int(hour_counter.get(hour, 0))}
            for hour in range(24)
        ],
        "weekdayDistribution": [
            {"weekday": index, "label": label, "value": int(weekday_counter.get(index, 0))}
            for index, label in enumerate(["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        ],
        "topTitles": top_titles,
    }


def build_personality_profile(
    days: int = 90,
    movies: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    days = max(7, min(int(days or 90), 365))
    now = now or datetime.now()
    start_date = now.date() - timedelta(days=days - 1)
    start_at = datetime.combine(start_date, datetime.min.time())
    movies = list(movies) if movies is not None else lib.load_library()
    events = _events_in_window(events if events is not None else db_service.load_behavior_events(), start_at, now)
    features = _build_features(movies, events, days)

    if not _has_enough_data(features):
        profile = _personality_payload("XXX", 0, 0, 0, features["confidence"])
        profile["dataStatus"] = "insufficient"
    else:
        focus_score = _focus_score(features)
        depth_score = _depth_score(features)
        routine_score = _routine_score(features)
        code = ("F" if focus_score >= 50 else "S") + ("D" if depth_score >= 50 else "W") + ("R" if routine_score >= 50 else "C")
        profile = _personality_payload(code, focus_score, depth_score, routine_score, _confidence(features, focus_score, depth_score, routine_score))
        profile["dataStatus"] = "ready"

    profile["sample"] = _sample_payload(features)
    profile["evidence"] = _evidence(features)
    profile["charts"] = _charts(features)
    return profile


def _build_features(movies: list[dict[str, Any]], events: list[dict[str, Any]], days: int) -> dict[str, Any]:
    viewing_units = _viewing_units(movies)
    watched = [unit for unit in viewing_units if _is_watched(unit)]
    completed = [unit for unit in watched if _playback_percent(unit) >= 90]
    unique_play_start_ids = _deduplicated_play_start_ids(events)
    play_events = [e for e in events if _normalize_event_type(e.get("event_type")) == "play_start" and id(e) in unique_play_start_ids]
    heartbeat_events = [e for e in events if e.get("event_type") == "play_heartbeat"]
    seek_forward = [e for e in events if e.get("event_type") == "seek_forward"]
    seek_backward = [e for e in events if e.get("event_type") == "seek_backward"]
    pause_events = [e for e in events if e.get("event_type") == "pause"]

    watch_seconds = sum(_watch_delta_seconds(e.get("delta_seconds")) for e in heartbeat_events)

    speed_seconds = sum(
        _watch_delta_seconds(e.get("delta_seconds"))
        for e in heartbeat_events
        if _safe_float(e.get("playback_rate"), 1) > 1.05
    )
    speed_usage_rate = _ratio(speed_seconds, watch_seconds)
    if speed_usage_rate == 0:
        fast_rate_changes = len([e for e in events if e.get("event_type") == "rate_change" and _safe_float(e.get("playback_rate"), 1) > 1.05])
        speed_usage_rate = min(100, fast_rate_changes * 12)

    daily_seconds: dict[str, float] = defaultdict(float)
    hour_counter: Counter[int] = Counter()
    weekday_counter: Counter[int] = Counter()
    source_counter: Counter[str] = Counter()
    movie_play_counts: Counter[str] = Counter()

    active_dates = set()
    for event in events:
        event_type = _normalize_event_type(event.get("event_type"))
        if event_type == "play_start" and id(event) not in unique_play_start_ids:
            continue
        if event_type not in {"play_start", "play_heartbeat", "play_end"}:
            continue
        dt = _parse_time(event.get("created_at"))
        if not dt:
            continue
        active_dates.add(dt.date().isoformat())
        delta = _watch_delta_seconds(event.get("delta_seconds"))
        if event_type == "play_start":
            hour_counter[dt.hour] += 1
            weekday_counter[dt.weekday()] += 1
            movie_id = str(event.get("movie_id") or "")
            if movie_id:
                movie_play_counts[movie_id] += 1
            source_counter[str(event.get("source_page") or "unknown")] += 1
        if delta:
            daily_seconds[dt.date().isoformat()] += delta

    category_counter: Counter[str] = Counter()
    favorite_category_counter: Counter[str] = Counter()
    # 题材白名单（与推荐画像同一套归一口径，滤除 2160p/HEVC 等技术噪声）
    try:
        valid_genre_names = genre_taxonomy.build_canonical_name_set(
            db_service.get_genre_map("movie"), db_service.get_genre_map("tv"))
    except Exception:
        valid_genre_names = set()
    for movie in watched:
        category_counter[_primary_label(movie, valid_genre_names)] += 1
    for movie in movies:
        if movie.get("is_favorite") or movie.get("isFavorite"):
            favorite_category_counter[_primary_label(movie, valid_genre_names)] += 1

    session_minutes = [
        _watch_delta_seconds(e.get("delta_seconds")) / 60
        for e in heartbeat_events
        if _watch_delta_seconds(e.get("delta_seconds")) > 0
    ]

    top_counts = [count for _label, count in category_counter.most_common()]
    genre_total = sum(top_counts)
    entropy = _entropy(top_counts)
    max_entropy = math.log2(max(2, len(top_counts))) if top_counts else 1
    genre_diversity = _clamp(entropy / max_entropy * 100 if max_entropy else 0)
    revisit_base = len(set(movie_play_counts)) or len(watched)

    return {
        "days": days,
        "moviesTotal": len(movies),
        "viewingUnitCount": len(viewing_units),
        "watchedCount": len(watched),
        "completedCount": len(completed),
        "activeDays": len(active_dates),
        "eventCount": len(play_events) + len(heartbeat_events),
        "playCount": len(play_events),
        "watchSeconds": int(watch_seconds),
        "completionRate": _ratio(len(completed), len(watched)),
        "abandonRate": _ratio(len([m for m in watched if 0 < _playback_percent(m) < 15]), len(watched)),
        "speedUsageRate": speed_usage_rate,
        "fastForwardRate": _ratio(len(seek_forward), max(1, len(play_events))),
        "rewindRate": _ratio(len(seek_backward), max(1, len(play_events))),
        "pauseRate": _ratio(len(pause_events), max(1, watch_seconds / 3600)),
        "revisitRate": _ratio(len([mid for mid, count in movie_play_counts.items() if mid and count >= 3]), max(1, revisit_base)),
        "avgSessionMinutes": round(sum(session_minutes) / len(session_minutes), 1) if session_minutes else 0,
        "sessionStability": _stability_score(session_minutes),
        "genreDiversity": genre_diversity,
        "top1GenreRatio": _ratio(top_counts[0] if top_counts else 0, genre_total),
        "top2GenreRatio": _ratio(sum(top_counts[:2]), genre_total),
        "top3GenreRatio": _ratio(sum(top_counts[:3]), genre_total),
        "coveredGenreCount": len(category_counter),
        "hourConcentration": _ratio(max(hour_counter.values() or [0]), sum(hour_counter.values())),
        "dailyStability": _stability_score(list(daily_seconds.values())),
        "categoryCounter": category_counter,
        "favoriteCategoryCounter": favorite_category_counter,
        "hourCounter": hour_counter,
        "weekdayCounter": weekday_counter,
        "sourceCounter": source_counter,
        "dailySeconds": daily_seconds,
        "confidence": _sample_confidence(len(watched), len(active_dates), watch_seconds, len(events)),
    }


def _focus_score(features: dict[str, Any]) -> float:
    return _clamp(
        features["completionRate"] * 0.38
        + (100 - features["speedUsageRate"]) * 0.16
        + (100 - features["fastForwardRate"]) * 0.14
        + features["rewindRate"] * 0.08
        + features["sessionStability"] * 0.12
        + min(100, features["avgSessionMinutes"] / 90 * 100) * 0.12
    )


def _depth_score(features: dict[str, Any]) -> float:
    concentration = max(features["top1GenreRatio"], features["top2GenreRatio"] * 0.82, features["top3GenreRatio"] * 0.68)
    return _clamp(concentration * 0.42 + (100 - features["genreDiversity"]) * 0.24 + features["revisitRate"] * 0.22 - min(100, features["coveredGenreCount"] * 10) * 0.08 + 16)


def _routine_score(features: dict[str, Any]) -> float:
    weekly_target = max(1, features["days"] / 7)
    return _clamp(features["hourConcentration"] * 0.42 + features["dailyStability"] * 0.26 + features["sessionStability"] * 0.18 + min(100, features["activeDays"] / weekly_target * 35) * 0.14)


def _personality_payload(code: str, focus_score: float, depth_score: float, routine_score: float, confidence: float) -> dict[str, Any]:
    name, tags, summary = PERSONALITIES.get(code, PERSONALITIES["XXX"])
    long_copy = PERSONALITY_LONG_COPY.get(code, PERSONALITY_LONG_COPY["XXX"])
    return {
        "code": code,
        "name": name,
        "title": name,
        "tags": tags,
        "summary": summary,
        "description": long_copy["description"],
        "typicalDay": long_copy["typicalDay"],
        "confidence": round(_clamp(confidence), 1),
        "algorithmVersion": "moviepop-fdw-v1",
        "dimensions": [
            _dimension("focus", "碎片", "聚焦", focus_score, "S", "F"),
            _dimension("depth", "泛览", "深耕", depth_score, "W", "D"),
            _dimension("routine", "随性", "规律", routine_score, "C", "R"),
        ],
        "scores": {"focus": round(focus_score, 1), "depth": round(depth_score, 1), "routine": round(routine_score, 1)},
        "letterScores": {
            "F": round(_clamp(focus_score), 1),
            "S": round(100 - _clamp(focus_score), 1),
            "D": round(_clamp(depth_score), 1),
            "W": round(100 - _clamp(depth_score), 1),
            "R": round(_clamp(routine_score), 1),
            "C": round(100 - _clamp(routine_score), 1),
        },
    }


def _dimension(key: str, left: str, right: str, score: float, left_code: str, right_code: str) -> dict[str, Any]:
    right_score = round(_clamp(score), 1)
    left_score = round(100 - _clamp(score), 1)
    return {
        "key": key,
        "left": left,
        "right": right,
        "leftCode": left_code,
        "rightCode": right_code,
        "leftScore": left_score,
        "rightScore": right_score,
        "score": right_score,
        "winner": right_code if right_score >= 50 else left_code,
    }


def _evidence(features: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": "completionRate", "label": "完播率", "value": round(features["completionRate"], 1), "unit": "%"},
        {"key": "speedUsageRate", "label": "倍速使用率", "value": round(features["speedUsageRate"], 1), "unit": "%"},
        {"key": "fastForwardRate", "label": "快进频率", "value": round(features["fastForwardRate"], 1), "unit": "%"},
        {"key": "rewindRate", "label": "回拉频率", "value": round(features["rewindRate"], 1), "unit": "%"},
        {"key": "top2GenreRatio", "label": "TOP2题材占比", "value": round(features["top2GenreRatio"], 1), "unit": "%"},
        {"key": "hourConcentration", "label": "固定时段集中度", "value": round(features["hourConcentration"], 1), "unit": "%"},
        {"key": "activeDays", "label": "活跃天数", "value": features["activeDays"], "unit": "天"},
    ]


def _charts(features: dict[str, Any]) -> dict[str, Any]:
    category_total = max(1, sum(features["categoryCounter"].values()))
    source_total = max(1, sum(features["sourceCounter"].values()))
    return {
        "genreDistribution": [{"label": label, "value": count, "percent": round(count / category_total * 100, 1)} for label, count in features["categoryCounter"].most_common(10)],
        "watchHourHeatmap": [{"hour": hour, "label": f"{hour:02d}:00", "value": features["hourCounter"].get(hour, 0)} for hour in range(24)],
        "weekdayDistribution": [{"weekday": index, "label": label, "value": features["weekdayCounter"].get(index, 0)} for index, label in enumerate(["周一", "周二", "周三", "周四", "周五", "周六", "周日"])],
        "operationProfile": [
            {"label": "倍速", "value": round(features["speedUsageRate"], 1)},
            {"label": "快进", "value": round(features["fastForwardRate"], 1)},
            {"label": "回拉", "value": round(features["rewindRate"], 1)},
            {"label": "暂停", "value": round(min(100, features["pauseRate"]), 1)},
        ],
        "sourceRoutes": [{"label": label, "value": count, "percent": round(count / source_total * 100, 1)} for label, count in features["sourceCounter"].most_common(8)],
    }


def _sample_payload(features: dict[str, Any]) -> dict[str, Any]:
    return {
        "days": features["days"],
        "viewingUnitCount": features.get("viewingUnitCount", features["watchedCount"]),
        "watchedCount": features["watchedCount"],
        "activeDays": features["activeDays"],
        "eventCount": features["eventCount"],
        "watchSeconds": features["watchSeconds"],
        "watchHours": round(features["watchSeconds"] / 3600, 1),
    }


def _has_enough_data(features: dict[str, Any]) -> bool:
    return features["watchedCount"] >= 2 and features["activeDays"] >= 1 and features["watchSeconds"] >= 30 * 60


def _confidence(features: dict[str, Any], focus_score: float, depth_score: float, routine_score: float) -> float:
    margin = (abs(focus_score - 50) + abs(depth_score - 50) + abs(routine_score - 50)) / 3
    return _clamp(features["confidence"] * 0.72 + min(100, margin * 2.2) * 0.28)


def _sample_confidence(watched_count: int, active_days: int, watch_seconds: float, event_count: int) -> float:
    return _clamp(min(100, watched_count / 12 * 100) * 0.35 + min(100, active_days / 10 * 100) * 0.25 + min(100, watch_seconds / (20 * 3600) * 100) * 0.25 + min(100, event_count / 120 * 100) * 0.15)


def _viewing_units(movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for movie in movies:
        playback = _playback(movie)
        episodes = playback.get("episodes") if isinstance(playback.get("episodes"), dict) else {}
        episode_units = []
        for episode_id, episode_playback in episodes.items():
            if not isinstance(episode_playback, dict):
                continue
            unit = dict(movie)
            unit["id"] = f"{movie.get('id', '')}::{episode_id}"
            unit["playback"] = episode_playback
            unit["episode_id"] = episode_playback.get("episode_id") or episode_id
            unit["episode_number"] = episode_playback.get("episode_number", 0)
            episode_units.append(unit)
        if episode_units:
            units.extend(episode_units)
        else:
            units.append(movie)
    return units


def _streak_summary(active_dates: set[str], today) -> tuple[int, int]:
    parsed_dates = set()
    for value in active_dates:
        try:
            parsed_dates.add(datetime.fromisoformat(str(value)).date())
        except ValueError:
            continue

    if not parsed_dates:
        return 0, 0

    current_streak = 0
    cursor = today
    while cursor in parsed_dates:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    streak = 0
    previous = None
    for current in sorted(parsed_dates):
        if previous and current == previous + timedelta(days=1):
            streak += 1
        else:
            streak = 1
        longest_streak = max(longest_streak, streak)
        previous = current
    return current_streak, longest_streak


def _primary_label(movie: dict[str, Any], valid_genre_names: set[str] | None = None) -> str:
    """统计口径的主题材：genres/tags 中第一个能归一进题材白名单的词。

    白名单为空或全部标签都是噪声（2160p/HEVC…）时回退到分类（动漫/剧集/电影）。
    """
    valid = valid_genre_names or set()
    for key in ("genres", "tags"):
        value = movie.get(key)
        raw_items: list[str] = []
        if isinstance(value, list):
            raw_items = [str(i).strip() for i in value if str(i).strip()]
        elif isinstance(value, str) and value.strip():
            raw_items = [p.strip() for p in value.replace("/", ",").split(",") if p.strip()]
        for text in raw_items:
            canon = genre_taxonomy.canonicalize_tag(text, valid) if valid else ()
            if canon:
                return canon[0]
    return _category(movie)


def _category(movie: dict[str, Any]) -> str:
    value = str(movie.get("category") or "").strip().lower()
    if value in {"anime", "动画", "动漫", "番剧"}:
        return "动漫"
    if value in {"series", "tv", "剧集", "电视剧"}:
        return "剧集"
    if value in {"movie", "电影"}:
        return "电影"
    return value or "其他"


def _playback(movie: dict[str, Any]) -> dict[str, Any]:
    playback = movie.get("playback")
    return playback if isinstance(playback, dict) else {}


def _playback_percent(movie: dict[str, Any]) -> float:
    return _safe_float(_playback(movie).get("percent"))


def _current_time(movie: dict[str, Any]) -> int:
    return int(max(0, _safe_float(_playback(movie).get("current_time"))))


def _watch_seconds(movie: dict[str, Any]) -> int:
    return int(max(0, _safe_float(_playback(movie).get("watch_seconds"))))


def _is_watched(movie: dict[str, Any]) -> bool:
    playback = _playback(movie)
    return _playback_percent(movie) > 0 or _current_time(movie) > 0 or bool(playback.get("last_play_time"))


def _normalize_event_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _events_in_window(events: list[dict[str, Any]], start_at: datetime, end_at: datetime) -> list[dict[str, Any]]:
    """Use parsed local datetimes instead of lexicographic ISO comparisons."""
    return [
        event for event in events
        if (created_at := _parse_time(event.get("created_at"))) and start_at <= created_at <= end_at
    ]


def _deduplicated_play_start_ids(events: list[dict[str, Any]], window_seconds: int = 12) -> set[int]:
    """Collapse the legacy preflight/player/stream start triplet into one play."""
    unique_ids: set[int] = set()
    last_start_by_target: dict[tuple[str, str], datetime] = {}
    sorted_events = sorted(events, key=lambda event: _parse_time(event.get("created_at")) or datetime.min)
    for event in sorted_events:
        if _normalize_event_type(event.get("event_type")) != "play_start":
            continue
        created_at = _parse_time(event.get("created_at"))
        if not created_at:
            unique_ids.add(id(event))
            continue
        target = (str(event.get("movie_id") or "").strip(), str(event.get("episode_id") or "").strip())
        previous = last_start_by_target.get(target)
        if previous and 0 <= (created_at - previous).total_seconds() <= window_seconds:
            continue
        unique_ids.add(id(event))
        last_start_by_target[target] = created_at
    return unique_ids


def _watch_delta_seconds(value: Any) -> float:
    """Keep a malformed heartbeat from overstating viewing time."""
    seconds = _safe_float(value)
    if not math.isfinite(seconds):
        return 0.0
    return min(120.0, max(0.0, seconds))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ratio(part: float, total: float) -> float:
    if not total:
        return 0
    return _clamp(float(part) / max(1.0, float(total)) * 100)


def _clamp(value: float, lower: float = 0, upper: float = 100) -> float:
    return max(lower, min(upper, float(value)))


def _entropy(values: list[int]) -> float:
    total = sum(values)
    if total <= 0:
        return 0
    result = 0.0
    for value in values:
        if value <= 0:
            continue
        p = value / total
        result -= p * math.log2(p)
    return result


def _stability_score(values: list[float]) -> float:
    values = [float(v) for v in values if float(v) > 0]
    if len(values) <= 1:
        return 35 if values else 0
    mean = sum(values) / len(values)
    if mean <= 0:
        return 0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    cv = math.sqrt(variance) / mean
    return _clamp(100 - cv * 70)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None
