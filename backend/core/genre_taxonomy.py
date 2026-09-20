"""题材词表归一化（阶段四推荐画像共用）。

背景：
- 用户本地片库 genres/tags 来源混杂：中文（动漫/动作冒险）、TMDB 英文（Sci-Fi & Fantasy）、
  技术噪声（2160p/HEVC/AAC/Japan/第一季）混杂；
- 虚拟片库 metadata_pool 的题材来自 TMDB movie/tv 两张独立词表，TV 部分类型 zh-CN 不翻译。

策略（白名单优于黑名单）：
- 以 TMDB movie 词表中文名为规范名集合；
- TV 英文类型 / 用户侧别名通过内置同义词归一到规范名；
- 不在规范词表内的标签一律丢弃（技术噪声天然被滤除）。
"""
from __future__ import annotations

# TV 题材 ID → 规范中文名（zh-CN 对部分 TV 类型不翻译，用 movie 词表口径兜底）
# 一个 TV 类型可对应多个规范题材（如 Sci-Fi & Fantasy = 科幻+奇幻）
TV_GENRE_ID_CANONICAL: dict[int, tuple[str, ...]] = {
    10759: ("动作", "冒险"),       # Action & Adventure
    10765: ("科幻", "奇幻"),       # Sci-Fi & Fantasy
    10768: ("战争",),              # War & Politics
    10762: ("儿童",),              # Kids（与"家庭"区分，画像时都保留）
    10769: ("剧情",),              # Soap（海外归类粗口径）
}

# 用户标签 / 英文类型名 → 规范名集合
_TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "动漫": ("动画",),
    "卡通": ("动画",),
    "anime": ("动画",),
    "animation": ("动画",),
    "animations": ("动画",),
    "动作冒险": ("动作", "冒险"),
    "action & adventure": ("动作", "冒险"),
    "sci-fi & fantasy": ("科幻", "奇幻"),
    "sci-fi": ("科幻",),
    "science fiction": ("科幻",),
    "war & politics": ("战争",),
    "tv movie": ("电视电影",),
}

# 纯噪声词（除白名单外的额外保险：这些词即使意外命中词表也不统计）
_EXPLICIT_NOISE = {
    "日本", "japan", "日本国", "美国", "中国", "韩国", "英国", "法国",
}

# 技术噪声正则（分辨率/编码/音频/季集/压制组特征），命中直接丢弃
_NOISE_SUFFIXES = (
    "p", "p60", "p30",
)


def _is_tech_noise(tag: str) -> bool:
    """识别分辨率/编码/音频等技术标签。"""
    t = tag.strip().lower()
    if not t:
        return True
    # 1080p / 2160p / 480p / 4k / 8k
    if t in {"4k", "8k"} or (t[:-1].isdigit() and t.endswith("p") and len(t) <= 5):
        return True
    if t in {
        "x264", "x265", "h264", "h265", "h.264", "h.265", "hevc", "avc", "av1",
        "aac", "flac", "dts", "truehd", "atmos", "ac3", "ddp", "dd5.1", "dts-hd",
        "web-dl", "webdl", "webrip", "bdrip", "bluray", "blu-ray", "remux", "hdtv", "dvdrip",
        "ma10p", "ma", "10bit", "8bit", "hdr", "hdr10", "dolbyvision", "dv",
        "ass", "srt", "sub", "chs", "cht", "gb", "big5",
    }:
        return True
    # 季/集标记：第一季 / S02 / Season 1
    if t.startswith("第") and t.endswith(("季", "集", "话", "部")):
        return True
    if t.startswith("s") and t[1:].isdigit():
        return True
    if t.startswith("season"):
        return True
    if t in _EXPLICIT_NOISE:
        return True
    return False


def _has_cjk(text: str) -> bool:
    """是否含 CJK 汉字（用于识别 TMDB zh-CN 已翻译的题材名；TV 部分类型不翻译仍为英文）。"""
    return any("一" <= ch <= "鿿" for ch in str(text or ""))


def build_canonical_name_set(genre_names_movie: dict[int, str],
                             genre_names_tv: dict[int, str] | None = None) -> set[str]:
    """构造规范题材名集合：只收中文名 + TV 内置兜底中文名。

    TV map 中未翻译的英文名（如 "Sci-Fi & Fantasy"）不得进入规范集，
    否则用户标签里的英文名会原样漏过白名单；那些 id 走 TV_GENRE_ID_CANONICAL 兜底。
    """
    names = {n for n in genre_names_movie.values() if n and _has_cjk(n)}
    if genre_names_tv:
        names.update(n for n in genre_names_tv.values() if n and _has_cjk(n))
    for ids in TV_GENRE_ID_CANONICAL.values():
        names.update(ids)
    return names


def canonicalize_tag(tag: str, valid_names: set[str]) -> tuple[str, ...]:
    """把单个用户标签归一为规范题材名元组；不是规范题材返回空元组（噪声丢弃）。"""
    raw = str(tag or "").strip()
    if not raw or _is_tech_noise(raw):
        return ()
    # 精确命中规范名
    if raw in valid_names:
        return (raw,)
    low = raw.lower()
    # 别名命中
    alias = _TAG_ALIASES.get(low)
    if alias:
        return tuple(n for n in alias if n in valid_names)
    # 含分隔符的复合标签（"科幻,动画"在 JSON 已拆开，这里兜底斜杠/竖线）
    if "/" in raw or "|" in raw:
        out: list[str] = []
        for part in raw.replace("|", "/").split("/"):
            out.extend(canonicalize_tag(part.strip(), valid_names))
        return tuple(dict.fromkeys(out))
    return ()


def map_genre_ids_to_names(genre_ids: list, media_type: str,
                           movie_map: dict[int, str], tv_map: dict[int, str]) -> list[str]:
    """TMDB 列表项 genre_ids → 规范中文名列表。

    movie/tv 各用各的 map（两套 id 体系不同）；TV 未翻译 id 用内置兜底表。
    输出统一为 movie 词表口径的规范名，供画像跨类型匹配。
    """
    names: list[str] = []
    for gid in genre_ids or []:
        try:
            gid_int = int(gid)
        except (TypeError, ValueError):
            continue
        if media_type == "tv":
            name = tv_map.get(gid_int)
            if not name:
                for canon in TV_GENRE_ID_CANONICAL.get(gid_int, ()):  # TV 英文未翻译兜底
                    if canon not in names:
                        names.append(canon)
                continue
            # TV map 里仍可能是英文名（Sci-Fi & Fantasy），转规范名
            canon = _TAG_ALIASES.get(name.lower())
            if canon:
                for c in canon:
                    if c not in names:
                        names.append(c)
            elif name and name not in names:
                names.append(name)
        else:
            name = movie_map.get(gid_int)
            if name and name not in names:
                names.append(name)
    return names
