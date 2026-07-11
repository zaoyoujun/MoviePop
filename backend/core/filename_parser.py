"""
文件名解析器
从视频文件名中提取标题、季号、集号、年份等信息
并合并同一系列/同一季的视频为逻辑条目
参考核心代码参考目录中的 utils/filename_parser.py 实现
"""
import hashlib
import logging
import os
import re
from collections import defaultdict
from urllib.parse import unquote

logger = logging.getLogger(__name__)

# 视频文件扩展名
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"}

# 年份匹配
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2}|21\d{2})(?!\d)")

# 集数匹配模式（按优先级排序）
EPISODE_PATTERNS = [
    re.compile(r"\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]", re.IGNORECASE),
    re.compile(r"\bE(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"[\[\s](?P<episode>\d{1,3})(?:v\d)?[\]\s]", re.IGNORECASE),
]

# 季数匹配模式
SEASON_PATTERNS = [
    re.compile(r"第\s*(?P<season>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*季", re.IGNORECASE),
    re.compile(r"\bSeason\s*(?P<season>\d{1,2})\b", re.IGNORECASE),
    re.compile(r"(?:^|[._])S(?P<season>\d{1,2})E\d{1,3}(?:$|[._])", re.IGNORECASE),
    re.compile(r"(?:^|[._\s])S\s*(?P<season>\d{1,2})(?:$|[._\s]|E)", re.IGNORECASE),
    re.compile(r"\bS\s*(?P<season>\d{1,2})\b", re.IGNORECASE),
    re.compile(r"\bS(?P<season>\d{1,2})\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<season>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*(?:部|期|章)", re.IGNORECASE),
    re.compile(r"\(\s*第\s*(?P<season>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*季[^)]*\)", re.IGNORECASE),
    re.compile(r"\b(?P<season>Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|Ⅵ|Ⅶ|Ⅷ|Ⅸ|Ⅹ|XI|XII|XIII|XIV|XV)\b", re.IGNORECASE),
]

# 部分编号匹配模式
PART_PATTERNS = [
    re.compile(r"#\s*(?P<part>\d{1,2})\b", re.IGNORECASE),
    re.compile(r"\bPart[\s.]*(?P<part>\d{1,2}|[IVX]+)\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<part>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*部分", re.IGNORECASE),
    re.compile(r"(?P<part>上|下|前篇|后篇|中篇)\b", re.IGNORECASE),
]

# 特殊类型匹配（OVA、剧场版等）
SPECIAL_TYPE_PATTERNS = {
    "OVA": re.compile(r"\b(?:OVA|OAD|OAV)\b", re.IGNORECASE),
    "特别篇": re.compile(r"\bSP\b|特别篇", re.IGNORECASE),
    "剧场版": re.compile(r"剧场版", re.IGNORECASE),
    "外传": re.compile(r"外传", re.IGNORECASE),
    "前传": re.compile(r"前传", re.IGNORECASE),
    "短篇": re.compile(r"短篇", re.IGNORECASE),
    "总集篇": re.compile(r"总集篇", re.IGNORECASE),
    "回顾": re.compile(r"回顾", re.IGNORECASE),
    "龙水篇": re.compile(r"龙水篇", re.IGNORECASE),
}

# 季数别名关键词
SEASON_ALIAS_KEYWORDS = {
    "最终季": 4,
    "Final Season": 4,
    "最终章": 4,
    "完结篇": 2,
    "续作": 2,
    "二期": 2,
    "三期": 3,
    "四期": 4,
    "新系列": 3,
    "新篇章": 2,
}

SEASON_TITLE_RULES = [
    (re.compile(r"(?<![A-Za-z0-9])Stone\s*Wars(?![A-Za-z])|石之战争", re.IGNORECASE), 2, "Stone Wars"),
    (re.compile(r"(?<![A-Za-z0-9])NEW\s*WORLD(?![A-Za-z])", re.IGNORECASE), 3, "NEW WORLD"),
    (re.compile(r"科学与未来|(?<![A-Za-z0-9])SCIENCE\s*FUTURE(?![A-Za-z])", re.IGNORECASE), 4, "科学与未来"),
]

# 媒体类型映射
MEDIA_CATEGORY_MAP = {
    "动漫": "动漫",
    "动画": "动漫",
    "anime": "动漫",
    "番剧": "动漫",
    "电视剧": "电视剧",
    "剧集": "电视剧",
    "tv": "电视剧",
    "电影": "电影",
}

# 挂载根、分类目录和临时目录不应该被当成片名。
IGNORED_TITLE_FOLDERS = {
    "quark",
    "115",
    "baidu",
    "openlist",
    "webdav",
    "local",
    "tmp",
    "temp",
    "电影",
    "电视剧",
    "剧集",
    "动漫",
    "动画",
    "番剧",
    "音乐",
    "movies",
    "movie",
    "series",
    "tv",
    "anime",
    "animation",
    "documents",
    "download",
    "downloads",
}

TITLE_ALIASES = {
    "Charlotte": ["シャーロット"],
    "石纪元": ["Dr. Stone", "ドクターストーン"],
    "葬送的芙莉莲": ["Frieren: Beyond Journey's End", "葬送のフリーレン"],
    "电锯人": ["Chainsaw Man", "チェンソーマン"],
}

ANIMATION_MOVIES = {
    "玩具总动员", "Toy Story",
    "怪兽电力公司", "Monsters, Inc.",
    "海底总动员", "Finding Nemo",
    "超人总动员", "The Incredibles",
    "赛车总动员", "Cars",
    "飞屋环游记", "Up",
    "神偷奶爸", "Despicable Me",
    "功夫熊猫", "Kung Fu Panda",
    "疯狂动物城", "Zootopia",
    "冰雪奇缘", "Frozen",
    "寻梦环游记", "Coco",
    "蜘蛛侠：平行宇宙", "Spider-Man: Into the Spider-Verse",
    "蜘蛛侠：纵横宇宙", "Spider-Man: Across the Spider-Verse",
    "蜘蛛侠：超越宇宙", "Spider-Man: Beyond the Spider-Verse",
    "蜘蛛侠：暗影蜘蛛侠", "Spider-Man: Into the Spider-Verse",
}

# 已知压制组名称（用于清理）
KNOWN_GROUPS = [
    "MAI",
    "Sakurato",
    "Kamigami",
    "UHA-WINGS",
    "UHA",
    "VCB-Studio",
    "LoliHouse",
    "ANi",
]

# 视频元信息噪声词（分辨率、编码格式等）
NOISE_PATTERNS = [
    r"\b(?:WEB[-_. ]?DL|WEB[-_. ]?RIP|BLU[-_. ]?RAY|BDRIP|REMUX|HDRIP|DVDRIP|HDTV|UHD|4K|1080P|720P|2160P)\b",
    r"\b(?:X264|X265|H264|H265|HEVC|AVC|AAC(?:\d\.\d)?|DTS(?:-HD)?|TRUEHD|ATMOS|DDP?\d\.\d|FLAC)\b",
    r"\b(?:NF|NFX|AMZN|DSNP|HMAX|BILI|BILIBILI)\b",
]

# 括号内容匹配
BRACKET_CONTENT = re.compile(r"[\[\(（【](.*?)[\]\)）】]")

# 罗马数字映射
ROMAN_MAP = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5,
    "Ⅵ": 6, "Ⅶ": 7, "Ⅷ": 8, "Ⅸ": 9, "Ⅹ": 10,
}

# 中文数字映射（包含大写）
CN_NUM_MAP = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5,
    "陆": 6, "柒": 7, "捌": 8, "玖": 9, "拾": 10,
}

CN_NUM_TEXT = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def _path_parts(decoded_path: str) -> list[str]:
    """解析路径为组件列表"""
    normalized = str(decoded_path or "").replace("\\", "/")
    return [part for part in normalized.split("/") if part]


def _normalize_text(text: str) -> str:
    """标准化文本：解码 URL 编码，替换下划线为空格"""
    return unquote(str(text or "")).replace("_", " ").strip()


def _clean_text(text: str) -> str:
    """清理文本中的噪声信息"""
    value = _normalize_text(text)
    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[国粤英日中韩]{1,4}\d*音轨", " ", value)
    value = re.sub(r"S\d{1,2}E\d{1,3}", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{1,2}x\d{1,3}\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"第\s*\d{1,3}\s*[集话話]", " ", value)
    value = re.sub(r"(?:Season\s*\d+|\bS\d{1,2}\b|第\s*[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+\s*(?:季|部|期|章))", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[[0-9]{1,3}\s*-\s*[0-9]{1,3}\]", " ", value)
    value = YEAR_PATTERN.sub(" ", value)
    value = value.replace("/", " ").replace("\\", " ")
    value = re.sub(r"[\[\(（【].*?[\]\)）】]", " ", value)
    value = re.sub(r"[_\-.!]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _strip_trailing_part_number(text: str) -> tuple[str, int | None]:
    value = str(text or "").strip()
    match = re.search(r"(?:^|[\s._-])(?P<part>[1-9])$", value)
    if not match:
        return value, None
    return value[:match.start("part")].strip(" ._-"), int(match.group("part"))


def _part_display(text: str, part: int | None) -> str:
    value = str(text or "").strip()
    if not part:
        return value
    if re.fullmatch(r"Part\s*%s" % int(part), value, re.IGNORECASE):
        return f"Part{int(part)}"
    value = re.sub(r"#\s*%s\b" % int(part), str(int(part)), value, flags=re.IGNORECASE)
    value = re.sub(r"\bPart\s*%s\b" % int(part), str(int(part)), value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=\d)", "", value)
    return value


def _strip_special_marker(text: str, special_type: str) -> str:
    value = str(text or "").strip()
    marker = str(special_type or "").strip()
    if marker:
        value = re.sub(re.escape(marker), " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip(" ._-")


def _normalize_known_season_title(title: str, season: int | None, season_title: str, part: int | None) -> tuple[str, int | None, str, int | None]:
    value = str(title or "").strip()
    current_season = season
    current_title = str(season_title or "").strip()
    current_part = part
    for pattern, detected_season, detected_title in SEASON_TITLE_RULES:
        match = pattern.search(value)
        if not match:
            continue
        before = value[:match.start()].strip(" ._-")
        after = value[match.end():].strip(" ._-")
        if before:
            value = before
        if not current_season:
            current_season = detected_season
        if not current_title:
            current_title = detected_title
        if after and not current_part:
            cleaned_after, part_number = _strip_trailing_part_number(after)
            if part_number:
                current_part = part_number
            elif cleaned_after:
                current_title = f"{current_title} {cleaned_after}".strip()
        break
    value, trailing_part = _strip_trailing_part_number(value)
    if trailing_part and not current_part and current_title:
        current_part = trailing_part
    return value, current_season, current_title, current_part


def _is_ignored_title_folder(text: str) -> bool:
    """判断目录是否只是挂载根、分类名或临时目录。"""
    raw = _normalize_text(text).strip().lower()
    cleaned = _clean_text(text).lower()
    if not raw and not cleaned:
        return True
    if raw in IGNORED_TITLE_FOLDERS or cleaned in IGNORED_TITLE_FOLDERS:
        return True
    if raw.startswith("__preview_") or raw.startswith("tmp_"):
        return True
    return False


def _category_folder_index(parts: list[str]) -> int | None:
    for index, part in enumerate(parts):
        value = _normalize_text(part).strip().lower()
        if not value:
            continue
        if value in {key.lower() for key in MEDIA_CATEGORY_MAP}:
            return index
    return None


def _is_explicit_version_folder(raw: str, clean: str) -> bool:
    value = str(raw or clean or "").strip()
    raw_normalized = re.sub(r"[_\-.]+", " ", value).strip().lower()
    normalized = _clean_text(value).strip().lower()
    if not normalized and not raw_normalized:
        return False
    technical_tokens = [
        r"4k",
        r"8k",
        r"2160p",
        r"1080p",
        r"720p",
        r"uhd",
        r"hdr",
        r"dolby\s*vision",
        r"hdr10(?:\+)?",
        r"web\s*dl",
        r"web\s*rip",
        r"blu\s*ray",
        r"bdrip",
        r"remux",
        r"hdtv",
        r"x264",
        r"x265",
        r"h\.?264",
        r"h\.?265",
        r"hevc",
        r"avc",
    ]
    if re.fullmatch(r"(?:\s*(?:" + "|".join(technical_tokens) + r")\s*){1,6}", raw_normalized, re.IGNORECASE):
        return True
    exact_names = {
        "彩色版",
        "黑白版",
        "黑白原色版",
        "原色版",
        "导演剪辑版",
        "导剪版",
        "加长版",
        "未删减版",
        "无删减版",
        "剧场剪辑版",
        "tv版",
        "web版",
        "bd版",
        "蓝光版",
        "4k版",
        "remux版",
        "国语版",
        "粤语版",
        "日语版",
        "英语版",
        "中字版",
        "配音版",
        "原版",
        "新编集版",
        "dv杜比视界版",
        "杜比视界版",
        "sdr标准版",
        "sdr版",
        "hdr版",
        "hdr10版",
        "杜比全景声版",
        "全景声版",
    }
    if normalized in {item.lower() for item in exact_names}:
        return True
    patterns = [
        r"^(?:4k|8k|2160p|1080p|bd|blu-?ray|remux)\s*版$",
        r"^(?:director'?s?\s*cut|extended\s*cut|uncut|theatrical\s*cut)$",
        r"^(?:彩色|黑白|原色|导演剪辑|导剪|加长|未删减|无删减|修复|蓝光|国语|粤语|日语|英语|中字|配音).{0,6}版$",
        r".+版$",
    ]
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)


def _is_edition_or_chapter_folder(raw: str, clean: str) -> bool:
    normalized = _clean_text(raw or clean).strip().lower()
    if not normalized:
        return False
    names = {"原版", "新编集版", "specials", "extras"}
    if normalized in {name.lower() for name in names}:
        return True
    return bool(re.search(r"(篇|章|part\s*\d+|#\s*\d+|新版|重制版|编集版)$", str(raw or clean), re.IGNORECASE))


def _path_entries_after_category(folder_parts: list[str]) -> list[tuple[int, str, str]]:
    entries = [
        (index, str(part or "").strip(), _clean_text(part))
        for index, part in enumerate(folder_parts)
        if str(part or "").strip() and not _is_ignored_title_folder(part)
    ]
    category_index = _category_folder_index(folder_parts)
    if category_index is None:
        return entries
    return [entry for entry in entries if entry[0] > category_index]


def _same_title_key(left: str, right: str) -> bool:
    left_key = re.sub(r"[^\w\u4e00-\u9fff]", "", _clean_text(left)).lower()
    right_key = re.sub(r"[^\w\u4e00-\u9fff]", "", _clean_text(right)).lower()
    return bool(left_key and right_key and left_key == right_key)


def _version_display(raw: str, clean: str) -> str:
    raw_display = re.sub(r"[_\-.]+", " ", _normalize_text(raw)).strip()
    # _clean_text deliberately strips release tokens from titles.  Keep them for
    # version labels though, otherwise paths such as "4K HDR" become just "HDR".
    if _is_explicit_version_folder(raw, clean):
        return raw_display
    return _clean_text(clean) or raw_display


def _season_label_from_path(folder_parts: list[str], title: str, version_title: str = "") -> str:
    entries = _path_entries_after_category(folder_parts)
    if not entries:
        return ""
    base_title = _clean_text(title or entries[0][2])
    version_clean = _clean_text(version_title)
    labels: list[str] = []
    for _, raw, clean in entries[1:]:
        normalized = _normalize_text(raw).strip().lower()
        if normalized in {"specials", "extras", "特别篇", "番外篇", "番外", "剧场版"}:
            continue
        if not clean or _same_title_key(clean, base_title):
            continue
        if version_clean and _same_title_key(clean, version_clean):
            continue
        if _is_explicit_version_folder(raw, clean):
            continue
        detected_season, detected_title = _detect_season(raw)
        if detected_title:
            labels.append(detected_title)
            continue
        if detected_season:
            remainder = _clean_text(raw)
            remainder = re.sub(r"(?:^|\s)第\s*[0-9一二三四五六七八九十]+\s*季(?:$|\s)", " ", remainder)
            remainder = re.sub(r"(?:^|\s)S\d{1,2}(?:$|\s)", " ", remainder, flags=re.IGNORECASE)
            remainder = re.sub(r"(?:^|\s)Season\s*\d+(?:$|\s)", " ", remainder, flags=re.IGNORECASE)
            remainder = remainder.replace(base_title, "").strip()
            if remainder:
                labels.append(remainder)
            continue
        if _detect_special_type(raw):
            labels.append(clean)
            continue
        if _is_title_season_folder(clean, base_title):
            continue
        labels.append(clean)
    return " ".join(dict.fromkeys([label for label in labels if label])).strip()


def _is_title_season_folder(clean: str, base_title: str) -> bool:
    value = _clean_text(clean)
    base = _clean_text(base_title)
    value_key = re.sub(r"[^\w\u4e00-\u9fff]", "", value).lower()
    base_key = re.sub(r"[^\w\u4e00-\u9fff]", "", base).lower()
    if not value or not base or not value_key.startswith(base_key):
        return False
    suffix = value_key[len(base_key):]
    if suffix.startswith(base_key):
        suffix = suffix[len(base_key):]
    if not suffix:
        return True
    season_words = {"第一季", "第二季", "第三季", "第四季", "第五季", "第六季", "第七季", "第八季", "第九季", "第十季"}
    return suffix in season_words or bool(re.fullmatch(r"(?:s|season)?\d{1,2}", suffix, re.IGNORECASE))


def _title_and_version_from_path(folder_parts: list[str], episode: int | None) -> tuple[str, str]:
    cleaned = _path_entries_after_category(folder_parts)
    if len(cleaned) < 2:
        return "", ""

    category_index = _category_folder_index(folder_parts)
    if category_index is not None:
        entries = cleaned
        if not entries:
            return "", ""
        
        category_part = str(folder_parts[category_index] or "").strip().lower()
        if category_part in {"电影", "movies"}:
            if len(entries) >= 2:
                has_version = any(_is_explicit_version_folder(entry[1], entry[2]) for entry in entries[1:])
                
                if len(entries) >= 3:
                    version_entry = next(
                        (entry for entry in entries[2:] if _is_explicit_version_folder(entry[1], entry[2])),
                        None,
                    )
                    movie_title = entries[1][2]
                    version_title = _version_display(version_entry[1], version_entry[2]) if version_entry else ""
                    return movie_title, version_title
                
                if has_version:
                    version_entry = next(
                        (entry for entry in entries[1:] if _is_explicit_version_folder(entry[1], entry[2])),
                        None,
                    )
                    movie_title = entries[0][2]
                    version_title = _version_display(version_entry[1], version_entry[2]) if version_entry else ""
                    return movie_title, version_title
                
                if len(entries) == 2:
                    return entries[1][2], ""
        
        version_entry = next(
            (entry for entry in entries[1:] if _is_explicit_version_folder(entry[1], entry[2])),
            None,
        )
        return entries[0][2], (_version_display(version_entry[1], version_entry[2]) if version_entry else "")

    # 没有分类目录时，也支持“片名/版本目录/文件”这种明确多层目录。
    parent_index, parent_raw, parent_clean = cleaned[-1]
    grand_index, _, grand_clean = cleaned[-2]
    if parent_index <= grand_index or not parent_raw or not grand_clean:
        return "", ""
    if (parent_clean and parent_clean == grand_clean) or _looks_like_season_folder(parent_raw):
        return "", ""
    if _is_explicit_version_folder(parent_raw, parent_clean):
        return grand_clean, _version_display(parent_raw, parent_clean)
    if episode is None:
        return "", ""
    return "", ""


def _movie_version_from_filename(filename_stem: str, category: str) -> str:
    if category != "电影":
        return ""
    parts = [part.strip() for part in re.split(r"\s+-\s+", str(filename_stem or "")) if part.strip()]
    if len(parts) < 2:
        return ""
    for candidate in reversed(parts[1:]):
        clean = _clean_text(candidate)
        if _is_explicit_version_folder(candidate, clean):
            return _version_display(candidate, clean)
    return ""


def _base_title_from_path(folder_parts: list[str]) -> str:
    category_index = _category_folder_index(folder_parts)
    
    if category_index is not None:
        for part in folder_parts[category_index + 1:]:
            if _is_ignored_title_folder(part) or _looks_like_season_folder(part):
                continue
            clean = _clean_text(part)
            if clean:
                return clean
        return ""
    
    for i in range(len(folder_parts) - 1, -1, -1):
        part = folder_parts[i]
        if _is_ignored_title_folder(part):
            continue
        if _looks_like_season_folder(part):
            continue
        if _is_explicit_version_folder(str(part), ""):
            continue
        clean = _clean_text(part)
        if clean:
            return clean
    
    return ""


def _matches_known_season_title(text: str) -> tuple[int | None, str]:
    value = str(text or "").strip()
    for pattern, season, title in SEASON_TITLE_RULES:
        if pattern.search(value):
            return season, title
    return None, ""


def _normalize_season_label(season: int | None, season_title: str, part: int | None) -> tuple[int | None, str, int | None]:
    value = str(season_title or "").strip()
    if not value:
        return season, value, part
    for pattern, known_season, known_title in SEASON_TITLE_RULES:
        match = pattern.search(value)
        if not match:
            continue
        current_season = season or known_season
        current_part = part
        before = value[:match.start()].strip(" ._-")
        after = value[match.end():].strip(" ._-#")
        title = known_title
        if before and not _same_title_key(before, known_title):
            title = f"{before} {title}".strip()
        if after and not current_part:
            cleaned_after, part_number = _strip_trailing_part_number(after)
            if part_number:
                current_part = part_number
            elif after.isdigit() and 0 < int(after) < 100:
                current_part = int(after)
            elif cleaned_after:
                title = f"{title} {cleaned_after}".strip()
        return current_season, title, current_part
    return season, value, part


def _edition_label_from_path(folder_parts: list[str], title: str) -> str:
    category_index = _category_folder_index(folder_parts)
    if category_index is None:
        return ""
    base = _clean_text(title)
    labels = []
    for part in folder_parts[category_index + 1:]:
        raw = str(part or "").strip()
        clean = _clean_text(raw)
        if not clean or clean == base or _looks_like_season_folder(raw) or _is_explicit_version_folder(raw, clean):
            continue
        if clean in {"原版", "新编集版"}:
            labels.append(clean)
    return " ".join(dict.fromkeys(labels))


def _extract_resolution(text: str) -> str:
    match = re.search(r"\b(4320p|2160p|1080p|720p|480p|8k|4k)\b", str(text or ""), re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).lower()
    return {"4k": "2160p", "8k": "4320p"}.get(value, value)


def _extract_codec(text: str) -> str:
    match = re.search(r"\b(HEVC|H\.?265|X265|AVC|H\.?264|X264|AV1|VP9)\b", str(text or ""), re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).upper().replace(".", "")
    return {"H265": "HEVC", "X265": "HEVC", "H264": "AVC", "X264": "AVC"}.get(value, value)


def _extract_release_group(*parts: str) -> str:
    text = " ".join(str(part or "") for part in parts)
    first = re.search(r"^\s*[\[\(（【]([^\]\)）】]{2,32})[\]\)）】]", text)
    if first:
        group = first.group(1).strip()
        if not re.search(r"\d{3,4}p|x26[45]|hevc|aac|flac|web", group, re.IGNORECASE):
            return group
    for group in KNOWN_GROUPS:
        if re.search(rf"\b{re.escape(group)}\b", text, re.IGNORECASE):
            return group
    return ""


def _extract_audio_info(text: str) -> str:
    value = str(text or "")
    tokens = []
    for pattern, label in [
        (r"\b(?:DDP|DD\+|EAC3)\s*5\.1\b", "DDP5.1"),
        (r"\bDTS(?:-HD)?\b", "DTS"),
        (r"\bTRUEHD\b", "TrueHD"),
        (r"\bATMOS\b", "Atmos"),
        (r"\bFLAC\b", "FLAC"),
        (r"\bAAC\b", "AAC"),
    ]:
        if re.search(pattern, value, re.IGNORECASE) and label not in tokens:
            tokens.append(label)
    return " / ".join(tokens)


def _extract_subtitle_info(text: str) -> str:
    value = str(text or "")
    tokens = []
    if re.search(r"\bASS\b|字幕|中字|简中|繁中|CHS|CHT", value, re.IGNORECASE):
        tokens.append("中文字幕")
    if re.search(r"\bPGS\b", value, re.IGNORECASE):
        tokens.append("PGS")
    return " / ".join(tokens)


def _parse_number(token: str | None) -> int | None:
    """解析数字（支持阿拉伯、罗马、中文数字）"""
    value = str(token or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    upper = value.upper()
    if upper in ROMAN_MAP:
        return ROMAN_MAP[upper]
    if value in CN_NUM_MAP:
        return CN_NUM_MAP[value]
    # 支持中文数字组合，如 "十二", "二十", "二十三"
    if len(value) == 2 and value.startswith("十") and value[1] in CN_NUM_MAP:
        return 10 + CN_NUM_MAP[value[1]]
    if len(value) == 2 and value.endswith("十") and value[0] in CN_NUM_MAP:
        return CN_NUM_MAP[value[0]] * 10
    if len(value) == 3 and value[1] in {"十", "拾"} and value[0] in CN_NUM_MAP and value[2] in CN_NUM_MAP:
        return CN_NUM_MAP[value[0]] * 10 + CN_NUM_MAP[value[2]]
    return None


def _cn_num_text(value: int | None) -> str:
    if not value:
        return ""
    n = int(value)
    if 0 <= n <= 10:
        return CN_NUM_TEXT[n]
    if n < 20:
        return f"十{CN_NUM_TEXT[n - 10]}"
    if n < 100:
        high, low = divmod(n, 10)
        return f"{CN_NUM_TEXT[high]}十{CN_NUM_TEXT[low] if low else ''}"
    return str(n)


def _extract_year(*parts: str) -> int | None:
    """从路径组件中提取年份"""
    for part in parts:
        match = YEAR_PATTERN.search(str(part or ""))
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2035:
                return year
    return None


def _detect_episode(text: str) -> int | None:
    """检测集数"""
    if not text:
        return None
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(str(text))
        if not match:
            continue
        try:
            return int(match.group("episode"))
        except Exception:
            continue
    range_match = re.search(r"\[(\d{1,3})\s*-\s*(\d{1,3})\]", str(text))
    if range_match:
        return int(range_match.group(1))
    return None


def _detect_special_type(*parts: str) -> str:
    """检测特殊类型（OVA、剧场版等）"""
    text = " ".join([str(part or "") for part in parts])
    for label, pattern in SPECIAL_TYPE_PATTERNS.items():
        if pattern.search(text):
            return label
    return ""


def _detect_part(*parts: str) -> int | None:
    """检测部分编号（如 #1, Part 2）"""
    text = " ".join([str(part or "") for part in parts])
    for pattern in PART_PATTERNS:
        match = pattern.search(text)
        if match:
            return _parse_number(match.group("part"))
    return None


def _detect_season(*parts: str) -> tuple[int | None, str]:
    """检测季数和季标题"""
    season_title = ""
    for part in parts:
        text = str(part or "")
        for pattern in SEASON_PATTERNS:
            match = pattern.search(text)
            if match:
                season = _parse_number(match.group("season"))
                if season:
                    # 提取主要副标题（如 NEW WORLD, Stone Wars）
                    main_title = ""
                    if "NEW WORLD" in text:
                        main_title = "NEW WORLD"
                    elif "Stone Wars" in text:
                        main_title = "Stone Wars"
                    elif "科学与未来" in text:
                        main_title = "科学与未来"
                    
                    # 提取部分编号（如 #1, #2）
                    part_suffix = ""
                    part_match = re.search(r"(#\s*\d+)\b", text)
                    if part_match:
                        part_suffix = part_match.group(1).strip()
                    
                    # 尝试从括号中提取季标题
                    bracket_match = re.search(r"\(\s*第\s*[0-9一二三四五六七八九十]+季\s*([^)]+)\)", text)
                    if bracket_match:
                        bracket_title = bracket_match.group(1).strip()
                        if bracket_title in {"上", "下", "前篇", "后篇", "中篇"}:
                            if main_title:
                                season_title = f"{main_title} {bracket_title}"
                            else:
                                season_title = bracket_title
                        else:
                            season_title = bracket_title
                    elif main_title:
                        season_title = main_title
                    
                    if part_suffix and part_suffix not in season_title:
                        if season_title:
                            season_title = f"{season_title} {part_suffix}"
                        else:
                            season_title = part_suffix
                    
                    return season, season_title
        for alias, season_num in SEASON_ALIAS_KEYWORDS.items():
            if alias.lower() in text.lower():
                return season_num, alias
    return None, season_title


def _extract_subtitle_from_path(*parts: str) -> tuple[str, int]:
    """从路径中提取副标题和数字前缀"""
    prefix_number = 0
    for part in parts:
        text = str(part or "")
        prefix_match = re.match(r"^(\d+)\.", text)
        if prefix_match:
            prefix_number = int(prefix_match.group(1))
        
        ova_match = re.search(r"\b(OVA|OAD|SP|特别篇|剧场版|外传|前传|短篇|总集篇)\s+(.+?)(?:\s*[-\[\(【#]|$)", text, re.IGNORECASE)
        if ova_match:
            subtitle = ova_match.group(2).strip()
            subtitle = re.sub(r"^[0-9]+\.\s*", "", subtitle)
            subtitle = re.sub(r"[\[\(（【].*?[\]\)）】]", "", subtitle).strip()
            for group in KNOWN_GROUPS:
                subtitle = re.sub(rf"\b{re.escape(group)}\b", "", subtitle, flags=re.IGNORECASE)
            subtitle = " ".join(subtitle.split()).strip()
            return subtitle, prefix_number
    return "", prefix_number


def _extract_chapter_name(*parts: str) -> str:
    """从路径中提取章节名（识别「XX篇」「XX章」「NEW WORLD #1」等模式）"""
    for part in parts:
        text = str(part or "")
        
        chapter_patterns = [
            re.compile(r"\b([\u4e00-\u9fff]{2,}篇)\b"),
            re.compile(r"\b([\u4e00-\u9fff]{2,}章)\b"),
            re.compile(r"\b(Chapter\s+\d+)\b", re.IGNORECASE),
            re.compile(r"\b([a-zA-Z][a-zA-Z0-9 ]{2,}Arc)\b", re.IGNORECASE),
            re.compile(r"\b([a-zA-Z][a-zA-Z0-9 ]{2,}Story)\b", re.IGNORECASE),
            re.compile(r"\b([a-zA-Z][a-zA-Z0-9 ]{2,}Edition)\b", re.IGNORECASE),
            re.compile(r"\b([A-Za-z][A-Za-z0-9 ]{2,})\s*#\s*\d+\b", re.IGNORECASE),
            re.compile(r"\b([\u4e00-\u9fff]{2,})\s*#\s*\d+\b"),
        ]
        
        for pattern in chapter_patterns:
            match = pattern.search(text)
            if match:
                chapter_name = match.group(1).strip()
                chapter_name = re.sub(r"^[0-9]+\.\s*", "", chapter_name)
                chapter_name = re.sub(r"[\[\(（【].*?[\]\)）】]", "", chapter_name).strip()
                for group in KNOWN_GROUPS:
                    chapter_name = re.sub(rf"\b{re.escape(group)}\b", "", chapter_name, flags=re.IGNORECASE)
                chapter_name = " ".join(chapter_name.split()).strip()
                if chapter_name and len(chapter_name) > 1:
                    return chapter_name
    
    return ""


def _infer_media_category(parts: list[str], season: int | None, special_type: str) -> str:
    """推断媒体类型（权重分级）"""
    text_blob = " ".join([str(part or "") for part in parts])
    lowered_text = text_blob.lower()
    
    for key, value in MEDIA_CATEGORY_MAP.items():
        if key.lower() in lowered_text:
            return value
    
    if special_type:
        if special_type in {"OVA", "OAD", "剧场版", "特别篇"}:
            return "动漫"
        return "电视剧" if any(token in lowered_text for token in ["电视剧", "tv", "series"]) else "动漫"
    
    if season is not None and season > 0:
        has_anime_keyword = any(token in lowered_text for token in ["动漫", "动画", "anime", "番剧"])
        if has_anime_keyword:
            return "动漫"
        
        for anime_title in TITLE_ALIASES:
            if anime_title.lower() in lowered_text:
                return "动漫"
        
        return "电视剧"
    
    episode_patterns = [
        re.compile(r"\bS\d{1,2}E\d{1,3}\b", re.IGNORECASE),
        re.compile(r"\b第\s*\d+\s*[集话話]\b", re.IGNORECASE),
    ]
    for pattern in episode_patterns:
        if pattern.search(text_blob):
            has_anime_keyword = any(token in lowered_text for token in ["动漫", "动画", "anime", "番剧"])
            if has_anime_keyword:
                return "动漫"
            
            for anime_title in TITLE_ALIASES:
                if anime_title.lower() in lowered_text:
                    return "动漫"
            
            return "电视剧"
    
    season_keywords = ["season", "第季", "第部", "第期", "第章"]
    if any(keyword in lowered_text for keyword in season_keywords):
        has_anime_keyword = any(token in lowered_text for token in ["动漫", "动画", "anime", "番剧"])
        if has_anime_keyword:
            return "动漫"
        
        for anime_title in TITLE_ALIASES:
            if anime_title.lower() in lowered_text:
                return "动漫"
        
        return "电视剧"
    
    folder_parts = parts[:-1] if parts else []
    clean_parts = [p for p in folder_parts if p and not _is_ignored_title_folder(p)]
    
    if len(clean_parts) >= 3:
        parent_is_version = _is_explicit_version_folder(clean_parts[-1], "") if clean_parts else False
        if parent_is_version:
            return "电影"
    
    return "电影"


def _looks_like_season_folder(text: str) -> bool:
    """判断是否为季文件夹"""
    if not text:
        return False
    if _detect_special_type(text):
        return True
    season, _ = _detect_season(text)
    if season:
        return True
    if _detect_part(text):
        return True
    for alias in SEASON_ALIAS_KEYWORDS:
        if alias.lower() in str(text).lower():
            return True
    if re.search(r"(篇|章|期|部分|合集|全集|重制版|新版)$", str(text)):
        return True
    return False


def _pick_title_candidate(parts: list[str], filename_stem: str, season: int | None, special_type: str) -> tuple[str, str]:
    """选择最合适的标题和季标签"""
    cleaned_parts = [
        str(part or "").strip()
        for part in parts
        if str(part or "").strip() and not _is_ignored_title_folder(part)
    ]
    season_label = ""
    
    if cleaned_parts:
        parent = cleaned_parts[-1]
        grand_parent = cleaned_parts[-2] if len(cleaned_parts) >= 2 else ""
        great_grand_parent = cleaned_parts[-3] if len(cleaned_parts) >= 3 else ""
        
        if _looks_like_season_folder(parent):
            if special_type:
                season_label = special_type
            elif season:
                detected_season, detected_title = _detect_season(parent)
                if detected_title and detected_title not in (f"S{int(season):02d}", f"第{season}季"):
                    season_label = detected_title
                else:
                    folder_title = _clean_text(parent)
                    if grand_parent:
                        folder_title = folder_title.replace(grand_parent, "").strip()
                    folder_title = re.sub(r"(?:^|\s)第\s*[0-9一二三四五六七八九十]+\s*季(?:$|\s)", " ", folder_title)
                    folder_title = re.sub(r"(?:^|\s)S\d{1,2}(?:$|\s)", " ", folder_title)
                    folder_title = re.sub(r"(?:^|\s)Season\s*\d+(?:$|\s)", " ", folder_title)
                    folder_title = folder_title.strip()
                    if folder_title:
                        season_label = folder_title
                    else:
                        season_label = f"第{_cn_num_text(int(season))}季"
            else:
                detected_season, detected_title = _detect_season(parent)
                if detected_season:
                    if detected_title and detected_title not in (f"S{int(detected_season):02d}", f"第{detected_season}季"):
                        season_label = detected_title
                    else:
                        season_label = f"第{_cn_num_text(int(detected_season))}季"
                else:
                    season_label = "第一季"
        
        # 处理特殊内容目录（特别收录）
        if special_type and grand_parent and grand_parent == "特别收录":
            candidate = _clean_text(great_grand_parent) if great_grand_parent else _clean_text(filename_stem)
            return candidate, season_label
        
        # 确定主标题
        if len(cleaned_parts) >= 2 and _looks_like_season_folder(parent):
            candidate = _clean_text(grand_parent)
        elif len(cleaned_parts) >= 1:
            candidate = _clean_text(parent)
        else:
            candidate = _clean_text(filename_stem)
        
        if not candidate:
            candidate = _clean_text(filename_stem)
        
        # 对于电影，检查文件名是否包含系列序号（如"飞驰人生2" vs "飞驰人生"）
        filename_clean = _clean_text(filename_stem)
        if candidate and filename_clean and filename_clean != candidate:
            if filename_clean.startswith(candidate) and len(filename_clean) > len(candidate):
                suffix = filename_clean[len(candidate):].strip()
                if suffix and suffix[0].isdigit():
                    candidate = filename_clean
        
        return candidate, season_label
    
    return _clean_text(filename_stem), season_label


def _season_display(season: int | None, season_title: str, special_type: str, part: int | None, hide_special: bool = False) -> str:
    tokens: list[str] = []
    if special_type and not hide_special:
        tokens.append(special_type)
    elif season and season > 1 and not season_title:
        tokens.append(f"第{_cn_num_text(int(season))}季")
    if season_title and season_title not in {"全集", "合集"}:
        if not (special_type and special_type in season_title):
            tokens.append(season_title)
    if part and part > 0 and not special_type:
        normalized_title = _part_display(str(season_title or ""), part)
        if str(part) not in normalized_title:
            tokens.append(str(part))
    season_label = f"第{_cn_num_text(int(season))}季" if season and season > 1 else ""
    if season_label and season_label not in season_title:
        tokens.append(season_label)
    text = " ".join(dict.fromkeys([token for token in tokens if token])).strip()
    return text


def _build_series_group(title: str, season: int | None, season_title: str, special_type: str, part: int | None, version_title: str = "") -> str:
    pieces = [title, str(season or 1), season_title or "", special_type or "", str(part or ""), version_title or ""]
    return "__".join(piece for piece in pieces if piece)


def _build_search_title(title: str, season: int | None, season_title: str, special_type: str, part: int | None = None, subtitle: str = "", episode: int | None = None, chapter_name: str = "", include_episode: bool = True) -> str:
    title_str = str(title or "").strip()
    season_title_str = str(season_title or "").strip()
    subtitle_str = str(subtitle or "").strip()
    chapter_name_str = str(chapter_name or "").strip()
    
    seen_tokens: set[str] = set()
    for token in title_str.lower().split():
        seen_tokens.add(token)
    
    pieces: list[str] = []
    if title_str:
        pieces.append(title_str)
    
    has_part = part and part > 0
    has_chapter = bool(chapter_name_str)
    
    if has_part and has_chapter:
        chapter_with_part = f"{chapter_name_str} Part{part}"
        pieces.append(chapter_with_part)
        for token in chapter_with_part.lower().split():
            seen_tokens.add(token)
    elif has_chapter:
        chapter_lower = chapter_name_str.lower()
        if not any(token in seen_tokens for token in chapter_lower.split()):
            pieces.append(chapter_name_str)
            for token in chapter_lower.split():
                seen_tokens.add(token)
    elif season_title_str and season_title_str not in {"全集", "合集"}:
        season_title_lower = season_title_str.lower()
        if not any(token in seen_tokens for token in season_title_lower.split()):
            pieces.append(season_title_str)
            for token in season_title_lower.split():
                seen_tokens.add(token)
    
    if subtitle_str:
        subtitle_lower = subtitle_str.lower()
        if not any(token in seen_tokens for token in subtitle_lower.split()):
            pieces.append(subtitle_str)
            for token in subtitle_lower.split():
                seen_tokens.add(token)
    
    if special_type:
        special_str = str(special_type).strip()
        special_lower = special_str.lower()
        if not any(token in seen_tokens for token in special_lower.split()):
            pieces.append(special_str)
            for token in special_lower.split():
                seen_tokens.add(token)
    
    if season and season > 1:
        season_label = f"第{_cn_num_text(int(season))}季"
        if season_label.lower() not in seen_tokens:
            pieces.append(season_label)
            seen_tokens.add(season_label.lower())
    
    if include_episode and episode:
        episode_str = f"第{episode}集"
        if episode_str.lower() not in seen_tokens:
            pieces.append(episode_str)
            seen_tokens.add(episode_str.lower())
    
    return " ".join(piece for piece in pieces if piece).strip()


def _dedupe_season_title(title: str, season_title: str) -> str:
    value = str(season_title or "").strip()
    base = _clean_text(title)
    clean_value = _clean_text(value)
    base_key = re.sub(r"[^\w\u4e00-\u9fff]", "", base).lower()
    value_key = re.sub(r"[^\w\u4e00-\u9fff]", "", clean_value).lower()
    if not value or not base:
        return value
    if clean_value == base or value_key == base_key:
        return ""
    if value_key.startswith(base_key):
        rest = value_key[len(base_key):]
        if rest.startswith(base_key):
            rest = rest[len(base_key):]
        if not rest:
            return ""
        if rest in {"第一季", "第二季", "第三季", "第四季", "第五季", "第六季", "第七季", "第八季", "第九季", "第十季"}:
            return ""
        if re.fullmatch(r"(?:s|season)?\d{1,2}", rest, re.IGNORECASE):
            return ""
    if base and base in clean_value:
        clean_value = clean_value.replace(base, "").strip()
        value = re.sub(r"\s+", " ", value.replace(base, "").strip())
        if clean_value:
            return value
    return value


def _franchise_from_parts(parts: list[str], title: str) -> str:
    for part in parts:
        text = str(part or "")
        if "合集" in text or "全集" in text:
            return _clean_text(text.replace("合集", "").replace("全集", ""))
    
    category_index = _category_folder_index(parts)
    
    if category_index is not None:
        category_part = str(parts[category_index] or "").strip().lower()
        if category_part in {"电影", "movies"}:
            for part in parts[category_index + 1:]:
                if _is_ignored_title_folder(part) or _looks_like_season_folder(part) or _is_explicit_version_folder(str(part or ""), ""):
                    continue
                clean = _clean_text(part)
                if clean and clean != title:
                    return clean
            return ""
    
    clean_parts = [
        part for part in parts
        if part and not _is_ignored_title_folder(part) and not _looks_like_season_folder(part) and not _is_explicit_version_folder(str(part), "")
    ]
    
    if len(clean_parts) >= 2:
        candidate = _clean_text(clean_parts[-2])
        title_clean = _clean_text(title)
        if candidate and candidate != title_clean:
            return candidate
    
    return ""


def _sort_bucket(category: str) -> int:
    return {"动漫": 0, "电视剧": 1, "电影": 2}.get(str(category or ""), 9)


def _media_type_from_category_and_title(category: str, title: str) -> str:
    if category == "动漫":
        return "动画"
    if category == "电视剧":
        return "剧集"
    
    title_lower = str(title or "").strip().lower()
    for anim_title in ANIMATION_MOVIES:
        if anim_title.lower() in title_lower:
            return "动画"
    
    return "电影"


def _sort_title(name: str) -> str:
    return re.sub(r"^[0-9]+\.", "", str(name or "")).strip().lower()


def _title_aliases(title: str, category: str) -> list[str]:
    aliases = []
    for key, values in TITLE_ALIASES.items():
        if key.lower() == str(title or "").strip().lower() or key in str(title or ""):
            aliases.extend(values)
    if category == "动漫" and re.fullmatch(r"[A-Za-z][A-Za-z0-9 .:'!-]{2,}", str(title or "").strip()):
        aliases.extend(TITLE_ALIASES.get(str(title or "").strip(), []))
    return list(dict.fromkeys([item for item in aliases if item]))


def _origin_countries(category: str) -> list[str]:
    if category == "动漫":
        return ["JP", "日本"]
    return []


def parse_video_filename(file_path: str) -> dict:
    """
    解析视频文件名，提取元信息
    :param file_path: 文件路径
    :return: 包含解析信息的字典
    """
    path_str = str(file_path or "")
    decoded_path = unquote(path_str)
    
    # 分离路径和文件名
    normalized = decoded_path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    
    if not parts:
        return {"name": "", "title": "", "category": "movie"}
    
    filename = parts[-1]
    filename_stem = filename
    
    # 移除扩展名
    for ext in VIDEO_EXTENSIONS:
        if filename.lower().endswith(ext):
            filename_stem = filename[:-len(ext)]
            break
    
    folder_parts = parts[:-1]
    text_blob = " ".join(parts)
    
    # 检测特殊类型
    special_type = _detect_special_type(filename_stem, *folder_parts[-4:])
    
    # 检测季数和季标题
    season, season_title = _detect_season(filename_stem, *folder_parts[-4:])
    
    # 检测集数
    episode = _detect_episode(filename_stem)
    path_title, version_title = _title_and_version_from_path(folder_parts, episode)
    
    # 检测部分编号
    part = _detect_part(filename_stem, *folder_parts[-4:])
    
    # 提取副标题和前缀编号
    subtitle, prefix_number = _extract_subtitle_from_path(*folder_parts[-4:])
    if prefix_number > 0 and not part:
        part = prefix_number
    
    # 提取章节名
    chapter_name = _extract_chapter_name(*folder_parts[-4:])
    
    # 推断媒体类型
    category = _infer_media_category(parts, season, special_type)
    file_version_title = _movie_version_from_filename(filename_stem, category)
    if file_version_title:
        version_title = file_version_title
    
    # 提取年份
    year = _extract_year(filename_stem, *folder_parts[-4:])
    
    # 选择标题和季标签
    main_title, season_label = _pick_title_candidate(folder_parts, filename_stem, season, special_type)
    if path_title:
        main_title = path_title
        path_season_label = _season_label_from_path(folder_parts, path_title, version_title)
        if path_season_label:
            season_label = path_season_label
        if not season_label and folder_parts:
            parent_label = str(folder_parts[-1] or "").strip()
            parent_clean = _clean_text(parent_label)
            if parent_clean and parent_clean != _clean_text(path_title) and (
                _is_edition_or_chapter_folder(parent_label, parent_clean) or _looks_like_season_folder(parent_label)
            ):
                season_label = parent_clean
    base_title = _base_title_from_path(folder_parts)
    known_season, known_season_title = _matches_known_season_title(main_title)
    if base_title and known_season_title and _clean_text(main_title) != _clean_text(base_title):
        main_title = base_title
        if not season:
            season = known_season
        if not season_title:
            season_title = known_season_title
        if not season_label:
            season_label = known_season_title
    hide_special_suffix = False
    if special_type and folder_parts and _detect_special_type(folder_parts[-1]):
        has_special_collection = any(part == "特别收录" for part in folder_parts)
        if has_special_collection:
            for i in range(len(folder_parts) - 1, -1, -1):
                if folder_parts[i] == "特别收录":
                    if i > 0:
                        main_title = _clean_text(folder_parts[i - 1])
                    break
            hide_special_suffix = True
        else:
            special_title = _strip_special_marker(_clean_text(folder_parts[-1] if folder_parts else ""), special_type)
            if special_title and special_title != _clean_text(main_title):
                if base_title and special_title != _clean_text(base_title):
                    main_title = f"{base_title} {special_title}".strip()
                    hide_special_suffix = True
                else:
                    main_title = special_title
    
    # 如果没有检测到季数但有季标签，尝试从季标签提取季数
    if season is None and season_label:
        inferred_season, _ = _detect_season(season_label)
        if inferred_season:
            season = inferred_season
    
    # 如果标题仍为空，使用文件名
    if not main_title:
        main_title = _clean_text(filename_stem)
    
    season_title = season_title or season_label
    season, season_title, part = _normalize_season_label(season, season_title, part)
    main_title, season, season_title, part = _normalize_known_season_title(main_title, season, season_title, part)
    season_title = _dedupe_season_title(main_title, season_title)
    display_suffix = _season_display(season, season_title, special_type, part, hide_special=hide_special_suffix)
    if display_suffix and str(display_suffix).startswith("（"):
        full_name = f"{main_title}{display_suffix}".strip()
    else:
        full_name = f"{main_title} {display_suffix}".strip() if display_suffix else main_title
    series_hint = (
        season is not None
        or episode is not None
        or bool(special_type)
        or any(_looks_like_season_folder(part_name) for part_name in folder_parts[-3:])
    )
    
    return {
        "name": main_title or filename_stem,
        "title": main_title or filename_stem,
        "full_name": full_name or main_title or filename_stem,
        "search_title": _build_search_title(main_title, season, season_title, special_type if not hide_special_suffix else "", part, subtitle, episode, chapter_name),
        "season": season or 1,
        "season_title": season_title,
        "version_title": version_title,
        "episode": episode,
        "part": part,
        "special_type": special_type,
        "subtitle": subtitle,
        "chapter_name": chapter_name,
        "prefix_number": prefix_number,
        "category": category,
        "aliases": _title_aliases(main_title, category),
        "origin_countries": _origin_countries(category),
        "media_type": _media_type_from_category_and_title(category, main_title or filename_stem),
        "year_hint": year,
        "resolution": _extract_resolution(text_blob),
        "video_codec": _extract_codec(text_blob),
        "audio_info": _extract_audio_info(text_blob),
        "subtitle_info": _extract_subtitle_info(text_blob),
        "release_group": _extract_release_group(filename_stem, *folder_parts[-3:]),
        "franchise": _franchise_from_parts(folder_parts, main_title),
        "sort_bucket": _sort_bucket(category),
        "sort_title": _sort_title(full_name or main_title),
        "series_group": _build_series_group(main_title, season, season_title, special_type, part, version_title) if series_hint else "",
        "type": "series" if series_hint else "movie",
        "path": file_path,
    }


def merge_series_videos(video_files: list, source_label: str = "") -> list:
    """
    将视频文件列表合并为逻辑条目（按系列/季分组）
    :param video_files: 视频文件路径列表或字典列表
    :param source_label: 数据源标签
    :return: 合并后的影片条目列表
    """
    groups = defaultdict(list)
    
    for item in video_files:
        if isinstance(item, dict):
            file_path = item.get("path", item.get("file_path", ""))
        else:
            file_path = str(item)
        
        if not file_path:
            continue
        
        parsed = parse_video_filename(file_path)
        title = parsed.get("title", "")
        season = parsed.get("season", 1)
        
        if not title:
            continue
        
        if parsed.get("category") == "电影" and parsed.get("version_title"):
            key = (title, parsed.get("version_title"))
        else:
            key = parsed.get("series_group") or (title, season)
        item_dict = item if isinstance(item, dict) else {}
        groups[key].append({
            "file_path": file_path,
            "parsed": parsed,
            **item_dict,
        })
    
    result = []
    seen_titles = set()
    
    for _, items in groups.items():
        # 提取第一条目的解析信息
        items.sort(key=lambda item: (
            int(item["parsed"].get("season") or 1),
            int(item["parsed"].get("episode") or 9999),
            str(item["parsed"].get("path") or item["file_path"]),
        ))
        first = items[0]["parsed"]
        title = first.get("title", "")
        season = int(first.get("season") or 1)
        season_title = first.get("season_title")
        version_title = first.get("version_title", "")
        special_type = first.get("special_type")
        category = first.get("category", "电影")
        year_hint = first.get("year_hint")
        
        # 收集所有集数和对应的文件路径
        episode_entries = []
        
        for index, item in enumerate(items, start=1):
            ep_num = item["parsed"].get("episode")
            episode_entries.append((int(ep_num or index), item["file_path"]))
        
        episode_entries.sort(key=lambda item: (item[0], item[1]))
        episodes = [ep for ep, _ in episode_entries]
        files = [file_path for _, file_path in episode_entries]
        
        # 判断是否为系列
        is_series = bool(
            first.get("type") == "series"
            or len(files) > 1
            or season > 1
            or special_type
            or category in {"动漫", "电视剧"}
        )
        if title in seen_titles and category != "电影":
            is_series = True
        seen_titles.add(title)
        episode_count = len(episodes) if is_series else 0
        
        # 构建条目ID
        id_parts = [title]
        if season > 1 or is_series:
            id_parts.append(f"S{season}")
        if season_title:
            id_parts.append(str(season_title))
        if version_title:
            id_parts.append(str(version_title))
        if special_type:
            id_parts.append(str(special_type))
        if first.get("part"):
            id_parts.append(f"Part{first.get('part')}")
        item_id = "_".join(id_parts)
        item_id = re.sub(r"[^\w\u4e00-\u9fff]", "_", item_id)
        
        # 获取第一集的文件路径作为代表（用于默认播放）
        first_file = files[0] if files else items[0]["file_path"]
        tags = [
            value for value in [
                category,
                first.get("resolution"),
                first.get("video_codec"),
                first.get("audio_info"),
                first.get("subtitle_info"),
                first.get("release_group"),
                version_title,
                season_title,
                special_type,
            ]
            if value
        ]
        aliases = []
        origin_countries = []
        for item in items:
            aliases.extend(item["parsed"].get("aliases") or [])
            origin_countries.extend(item["parsed"].get("origin_countries") or [])
        
        search_title = _build_search_title(
            title, season, season_title, special_type, 
            first.get("part"), first.get("subtitle"), 
            None if is_series else first.get("episode"), 
            first.get("chapter_name"),
            include_episode=not is_series
        )
        
        result.append({
            "id": item_id,
            "name": title,
            "title": title,
            "display_title": first.get("full_name") or title,
            "series_title": title,
            "search_title": search_title or title,
            "aliases": list(dict.fromkeys(aliases)),
            "origin_countries": list(dict.fromkeys(origin_countries)),
            "season": season,
            "season_title": season_title,
            "chapter_name": first.get("chapter_name"),
            "version_title": version_title,
            "part": first.get("part"),
            "episode_count": episode_count,
            "episodes": episodes if is_series else [],
            "is_series": is_series,
            "special_type": special_type,
            "category": category,
            "year_hint": year_hint,
            "source_label": source_label,
            "file_path": first_file,
            "files": files,
            "quality": first.get("resolution", ""),
            "subtitle_info": first.get("subtitle_info", ""),
            "release_group": first.get("release_group", ""),
            "video_codec": first.get("video_codec", ""),
            "audio_info": first.get("audio_info", ""),
            "franchise": first.get("franchise", ""),
            "sort_bucket": first.get("sort_bucket", 9),
            "sort_title": first.get("sort_title", ""),
            "cover_url": "",
            "backdrop_url": "",
            "intro": "",
            "rating": 0.0,
            "tags": list(dict.fromkeys(tags)),
        })
    
    # 按标题和季数排序
    result.sort(key=lambda x: (int(x.get("sort_bucket", 9)), x["title"], x["season"], x.get("season_title") or ""))
    
    return result
