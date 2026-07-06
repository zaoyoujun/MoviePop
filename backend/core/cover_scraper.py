import hashlib
import logging
import os
import re
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from requests import HTTPError

try:
    from backend.config import AppConfig
except ImportError:
    from config import AppConfig

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

ANIBK_BASE = "https://www.anibk.com"
ANIBK_SEARCH = f"{ANIBK_BASE}/list/---------?order=20&kw="
TMDB_BASE = "https://www.themoviedb.org"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w780"
TMDB_BACKDROP_BASE = "https://image.tmdb.org/t/p/original"
DOUBAN_BASE = "https://movie.douban.com"
BANGUMI_API = "https://api.bgm.tv"

COUNTRY_NAME_MAP = {
    "CN": "中国大陆",
    "HK": "中国香港",
    "TW": "中国台湾",
    "JP": "日本",
    "KR": "韩国",
    "US": "美国",
    "GB": "英国",
    "FR": "法国",
    "DE": "德国",
    "TH": "泰国",
    "IN": "印度",
}

# Cover storage must match the FastAPI /covers mount. In packaged builds,
# __file__ points inside PyInstaller's temporary extraction directory, while
# AppConfig.COVERS_DIR points at the portable data directory.
COVERS_DIR = AppConfig().COVERS_DIR
COVERS_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 杈呭姪鍑芥暟 ====================
def normalize_chinese_punctuation(text):
    # docstring removed after encoding cleanup
    if not text:
        return text
    replacements = {
        "：": ":",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "，": ",",
        "。": ".",
        "、": " ",
    }
    value = str(text)
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    return value


def clean_title_for_search(title):
    # docstring removed after encoding cleanup
    title = normalize_chinese_punctuation(title)
    season_num = None
    year = None

    season_match = re.search(r'第\s*(\d+)\s*季|Season\s*(\d+)|S(\d{1,2})', title, re.IGNORECASE)
    if season_match:
        season_num = next((g for g in season_match.groups() if g), None)
        if season_num:
            season_num = int(season_num)

    year_match = re.search(r'[(（](\d{4})[)）]', title)
    if year_match:
        year = year_match.group(1)

    clean_name = re.sub(r'第\s*\d+\s*季|Season\s*\d+|S\d{1,2}', '', title, flags=re.IGNORECASE)
    clean_name = re.sub(r'[(（]\d{4}[)）]', '', clean_name)
    clean_name = re.sub(r'[_\-\[\]().]', ' ', clean_name)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()

    return {
        "clean_name": clean_name,
        "season": season_num,
        "year": year,
        "original_title": title,
    }

def is_chinese(text):
    # docstring removed after encoding cleanup
    if not text:
        return True
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars) / max(1, len(text)) > 0.3


def translate_to_chinese(text):
    # docstring removed after encoding cleanup
    if not text or is_chinese(text):
        return text
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target='zh-CN').translate(text)
        logger.debug("Description translated successfully")
        return translated
    except Exception as e:
        logger.debug("Description translation failed: %s", e)
        return text

# ==================== 鏍稿績鍒墛绫?====================
class CoverScraper:
    # docstring removed after encoding cleanup

    def __init__(self):
        self.config = AppConfig()
        self.config.load_config()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if self.config.DOUBAN_COOKIE:
            self.session.headers.update({"Cookie": self.config.DOUBAN_COOKIE})
        self.session.verify = False
        self.session.trust_env = False  # 绂佺敤绯荤粺浠悊
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self._unreachable = False

    @staticmethod
    def _empty_result(year: int = 0) -> dict:
        return {
            "title": "",
            "cover_url": "",
            "backdrop_url": "",
            "description": "",
            "score": 0.0,
            "tags": [],
            "genres": [],
            "countries": [],
            "languages": [],
            "year": year,
            "duration": "",
            "metadata_source": "",
            "original_title": "",
            "tmdb_id": "",
            "tmdb_media_type": "",
            "season_tmdb_id": "",
            "season_title": "",
            "douban_url": "",
            "vote_count": 0,
        }

    @staticmethod
    def _category_kind(category: str) -> str:
        value = str(category or "").strip().lower()
        if value in {"anime", "动漫", "动画", "番剧"}:
            return "anime"
        if value in {"series", "电视剧", "剧集", "tv"}:
            return "series"
        return "movie"


    @staticmethod
    def _merge_metadata(primary: dict, secondary: dict, prefer_backdrop: bool = False, prefer_cover: bool = False) -> dict:
        merged = dict(primary or {})
        for key in (
            "title",
            "cover_url",
            "backdrop_url",
            "description",
            "year",
            "duration",
            "metadata_source",
            "original_title",
            "tmdb_id",
            "tmdb_media_type",
            "season_tmdb_id",
            "season_title",
            "douban_url",
            "vote_count",
        ):
            if (not merged.get(key)) and secondary.get(key):
                merged[key] = secondary[key]
        if prefer_backdrop and secondary.get("backdrop_url"):
            merged["backdrop_url"] = secondary["backdrop_url"]
        if prefer_cover and secondary.get("cover_url"):
            merged["cover_url"] = secondary["cover_url"]
        if not merged.get("cover_url") and secondary.get("cover_url"):
            merged["cover_url"] = secondary["cover_url"]
        if not merged.get("score") and secondary.get("score"):
            merged["score"] = secondary["score"]
        for key in ("tags", "genres", "countries", "languages"):
            values = []
            for source in (merged.get(key), secondary.get(key)):
                if isinstance(source, list):
                    values.extend(source)
            merged[key] = list(dict.fromkeys([str(item).strip() for item in values if str(item).strip()]))
        return merged

    @staticmethod
    def _has_metadata(value: dict) -> bool:
        return bool(value and (value.get("title") or value.get("cover_url") or value.get("description")))

    @staticmethod
    def _merge_douban_facts(primary: dict, douban_meta: dict, allow_cover: bool = False) -> dict:
        merged = dict(primary or {})
        if not douban_meta:
            return merged
        for key in ("score", "duration", "douban_url"):
            if douban_meta.get(key):
                merged[key] = douban_meta[key]
        if douban_meta.get("year") and not merged.get("year"):
            merged["year"] = douban_meta["year"]
        if douban_meta.get("description") and not merged.get("description"):
            merged["description"] = douban_meta["description"]
        if allow_cover and douban_meta.get("cover_url"):
            if not merged.get("cover_url"):
                merged["cover_url"] = douban_meta["cover_url"]
            if not merged.get("backdrop_url"):
                merged["backdrop_url"] = douban_meta.get("backdrop_url") or douban_meta["cover_url"]
        for key in ("tags", "genres", "countries", "languages"):
            values = []
            for source in (merged.get(key), douban_meta.get(key)):
                if isinstance(source, list):
                    values.extend(source)
            merged[key] = list(dict.fromkeys([str(item).strip() for item in values if str(item).strip()]))
        if douban_meta.get("metadata_source"):
            sources = [str(merged.get("metadata_source") or "").strip(), "douban"]
            merged["metadata_source"] = "+".join(dict.fromkeys([item for item in sources if item]))
        return merged

    @staticmethod
    def _merge_tmdb_artwork(primary: dict, tmdb_meta: dict, allow_cover: bool = False) -> dict:
        merged = dict(primary or {})
        if not tmdb_meta:
            return merged
        if tmdb_meta.get("backdrop_url"):
            merged["backdrop_url"] = tmdb_meta["backdrop_url"]
        elif not merged.get("backdrop_url") and tmdb_meta.get("cover_url"):
            merged["backdrop_url"] = tmdb_meta["cover_url"]
        if allow_cover and tmdb_meta.get("cover_url") and not merged.get("cover_url"):
            merged["cover_url"] = tmdb_meta["cover_url"]
        for key in ("tmdb_id", "tmdb_media_type", "season_tmdb_id", "season_title", "original_title", "vote_count"):
            if tmdb_meta.get(key) and not merged.get(key):
                merged[key] = tmdb_meta[key]
        if tmdb_meta.get("metadata_source"):
            sources = [str(merged.get("metadata_source") or "").strip(), "tmdb"]
            merged["metadata_source"] = "+".join(dict.fromkeys([item for item in sources if item]))
        return merged

    def scrape(self, title: str, category: str = "anime", year: int = 0, season: int = 1, 
               is_series: bool = False, season_title: str = "", aliases: list[str] | None = None,
               origin_countries: list[str] | None = None, chapter_name: str = "", part: int | None = None) -> dict:
        # docstring removed after encoding cleanup
        result = self._empty_result(year)
        if not title or len(title) < 2:
            return result

        if self._category_kind(category) == "anime":
            result = self._scrape_anibk(title, year, season, season_title, chapter_name, part)
            if not self._has_metadata(result):
                logger.debug("AniBK did not provide an exact anime result, trying Douban fallback: %s", title)
                result = self._scrape_douban(title, year, season, chapter_name, part)
                if not self._has_metadata(result):
                    result = self._scrape_tmdb(title, year, season, category, season_title, aliases, origin_countries, chapter_name, part)
                else:
                    tmdb_meta = self._scrape_tmdb(title, year, season, category, season_title, aliases, origin_countries, chapter_name, part)
                    result = self._merge_tmdb_artwork(result, tmdb_meta, allow_cover=False)
            else:
                douban_meta = self._scrape_douban(title, year, season, "", None)
                result = self._merge_douban_facts(result, douban_meta, allow_cover=False)
                tmdb_meta = self._scrape_tmdb(title, year, season, category, season_title, aliases, origin_countries, chapter_name, part)
                result = self._merge_tmdb_artwork(result, tmdb_meta, allow_cover=False)
            if not result.get("backdrop_url"):
                result["backdrop_url"] = result.get("cover_url", "")
            return result

        result = self._scrape_douban(title, year, season, chapter_name, part)
        if self._has_metadata(result):
            tmdb_meta = self._scrape_tmdb(title, year, season, category, season_title, aliases, origin_countries, chapter_name, part)
            result = self._merge_tmdb_artwork(result, tmdb_meta, allow_cover=False)
        else:
            result = self._scrape_tmdb(title, year, season, category, season_title, aliases, origin_countries, chapter_name, part)
            douban_meta = self._scrape_douban(title, year, season, chapter_name, part)
            result = self._merge_douban_facts(result, douban_meta, allow_cover=True)
        if not result.get("backdrop_url"):
            result["backdrop_url"] = result.get("cover_url", "")
        return result

    def _scrape_source_order(self, category: str) -> list[str]:
        source = str(getattr(self.config, "SCRAPE_SOURCE", "auto") or "auto").strip().lower()
        has_douban_cookie = bool(str(getattr(self.config, "DOUBAN_COOKIE", "") or "").strip())
        kind = self._category_kind(category)
        if source in {"douban", "tmdb", "anibk"}:
            first = source
            rest = [item for item in ("tmdb", "douban", "anibk") if item != first]
            return [item for item in [first, *rest] if item != "douban" or has_douban_cookie]
        if kind == "anime":
            order = ["anibk", "tmdb"]
            if has_douban_cookie:
                order.insert(1, "douban")
            return order
        order = ["douban", "tmdb"] if has_douban_cookie else ["tmdb"]
        return order

    def _build_douban_headers(self, ajax: bool = False) -> dict:
        headers = HEADERS.copy()
        headers.update({
            "Referer": f"{DOUBAN_BASE}/",
            "Origin": DOUBAN_BASE,
            "Sec-Fetch-Site": "same-origin",
        })
        if ajax:
            headers.update({
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
            })
        else:
            headers.update({
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Upgrade-Insecure-Requests": "1",
            })
        cookie = str(getattr(self.config, "DOUBAN_COOKIE", "") or "").strip()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _apply_douban_cookie(self, session: requests.Session) -> None:
        raw_cookie = str(getattr(self.config, "DOUBAN_COOKIE", "") or "").strip()
        if not raw_cookie:
            return
        try:
            parsed = SimpleCookie()
            parsed.load(raw_cookie)
            for morsel in parsed.values():
                session.cookies.set(
                    morsel.key,
                    morsel.value,
                    domain=".douban.com",
                    path=morsel["path"] or "/",
                )
        except Exception as exc:
            logger.warning("豆瓣 Cookie 解析失败: %s", exc)

    def _solve_douban_challenge(self, session: requests.Session, response: requests.Response) -> bool:
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            form = soup.find("form", id="sec")
            if not form:
                return False
            tok_input = form.find("input", {"name": "tok"})
            cha_input = form.find("input", {"name": "cha"})
            red_input = form.find("input", {"name": "red"})
            if not tok_input or not cha_input or not red_input:
                return False

            difficulty = 4
            difficulty_match = re.search(r"process\(data,\s*difficulty\s*=\s*(\d+)\)", response.text)
            if difficulty_match:
                difficulty = int(difficulty_match.group(1))

            cha = cha_input.get("value", "")
            nonce = 0
            prefix = "0" * difficulty
            while True:
                nonce += 1
                digest = hashlib.sha512(f"{cha}{nonce}".encode("utf-8")).hexdigest()
                if digest.startswith(prefix):
                    break

            headers = dict(session.headers)
            headers.update({
                "Referer": response.url,
                "Origin": "https://sec.douban.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            })
            challenge_url = urljoin(response.url, form.get("action") or "/c")
            challenge_response = session.post(
                challenge_url,
                data={
                    "tok": tok_input.get("value", ""),
                    "cha": cha,
                    "sol": str(nonce),
                    "red": red_input.get("value", ""),
                },
                headers=headers,
                timeout=20,
                allow_redirects=False,
            )
            return challenge_response.status_code in {200, 302, 303}
        except Exception as exc:
            logger.warning("豆瓣风控验证处理失败: %s", exc)
            return False

    def _douban_get(self, url: str, ajax: bool = False) -> requests.Response:
        session = requests.Session()
        session.verify = False
        session.trust_env = False
        session.headers.update(self._build_douban_headers(ajax=ajax))
        self._apply_douban_cookie(session)
        response = session.get(url, timeout=15, allow_redirects=True)
        if "sec.douban.com" in response.url or 'id="sec"' in response.text:
            logger.warning("豆瓣请求命中风控验证: %s", response.url)
            if self._solve_douban_challenge(session, response):
                response = session.get(url, timeout=15, allow_redirects=True)
        return response

    def _scrape_anibk(self, title: str, year: int = 0, season: int = 1, season_title: str = "", chapter_name: str = "", part: int | None = None) -> dict:
        result = self._empty_result(year)
        result["metadata_source"] = "anibk"
        queries = self._build_queries(title, year, season, season_title, chapter_name, part)
        logger.debug(f"AniBK queries: {queries}")

        candidates = []
        for query_index, q in enumerate(queries):
            cands = self._search_anibk(q)
            for c in cands:
                c["_query"] = q
                c["_query_index"] = query_index
                c["match_score"] = max(
                    self._score_candidate(title, season, year, c),
                    self._score_candidate(q, season, year, c),
                ) + self._season_title_bonus(season_title, c) + self._chapter_title_bonus(chapter_name, part, c)
            candidates.extend(cands)

        if not candidates:
            logger.debug("AniBK search returned no result")
            return result

        deduped = {}
        for candidate in candidates:
            key = candidate.get("url") or candidate.get("title")
            if not key:
                continue
            current = deduped.get(key)
            if current is None or float(candidate.get("match_score") or 0) > float(current.get("match_score") or 0):
                deduped[key] = candidate
        candidates = list(deduped.values())
        strict_candidates = [
            candidate for candidate in candidates
            if self._candidate_matches_detail(season_title, chapter_name, part, candidate)
        ]
        if strict_candidates:
            candidates = strict_candidates
        elif chapter_name or part:
            logger.debug(
                "AniBK rejected generic candidates for detail match: title=%s season_title=%s chapter=%s part=%s",
                title,
                season_title,
                chapter_name,
                part,
            )
            return result
        candidates.sort(key=lambda c: (c.get("match_score", 0), -int(c.get("_query_index") or 0)), reverse=True)
        best = candidates[0]
        if float(best.get("match_score") or 0) < 30:
            logger.debug(
                "AniBK best candidate rejected: target=%s candidate=%s score=%s",
                title,
                best.get("title", ""),
                best.get("match_score", 0),
            )
            return result
        logger.debug("AniBK matched title=%s", best["title"])
        detail_url = best["url"]

        result["title"] = best["title"]

        cover_url = self._get_anibk_cover(detail_url)
        if cover_url:
            local_cover = self._download_cover(cover_url, title, season, chapter_name, part)
            if local_cover:
                result["cover_url"] = local_cover

        intro = self._get_anibk_intro(detail_url)
        if intro:
            result["description"] = intro[:500]

        anibk_year = self._get_anibk_year(detail_url)
        if anibk_year:
            result["year"] = anibk_year

        result["match_score"] = best.get("match_score", 0)
        return result

    def _scrape_tmdb(
        self,
        title: str,
        year: int = 0,
        season: int = 1,
        category: str = "",
        season_title: str = "",
        aliases: list[str] | None = None,
        origin_countries: list[str] | None = None,
        chapter_name: str = "",
        part: int | None = None,
    ) -> dict:
        api_result = self._scrape_tmdb_api(title, year, season, category, season_title, aliases, origin_countries, chapter_name, part)
        if api_result.get("title") or api_result.get("cover_url"):
            return api_result
        return self._scrape_tmdb_web(title, year, chapter_name, part)

    def _build_queries(self, title: str, year: int = 0, season: int = 1, season_title: str = "", chapter_name: str = "", part: int | None = None) -> list:
        # docstring removed after encoding cleanup
        parsed = clean_title_for_search(title)
        clean_base = parsed["clean_name"] or title
        queries = []

        detail_name = str(chapter_name or "").strip() or str(season_title or "").strip()
        if detail_name and clean_base:
            if part and part > 0:
                queries.extend([
                    f"{clean_base} {detail_name} #{int(part)}",
                    f"{clean_base} {detail_name}{int(part)}",
                    f"{clean_base} {detail_name} Part{int(part)}",
                ])
            queries.append(f"{clean_base} {detail_name}")

        queries.append(clean_base)

        if season_title and clean_base:
            queries.append(f"{clean_base} {season_title}")

        if season > 1 and clean_base:
            queries.extend([
                f"{clean_base} 第{season}季",
                f"{clean_base} 第{self._cn_num(season)}季",
                f"{clean_base} Season {season}",
                f"{clean_base} S{season:02d}",
                f"{clean_base} S{season}",
            ])

        if year and clean_base:
            queries.append(f"{clean_base} {year}")

        return list(dict.fromkeys([q for q in queries if q]))
    @staticmethod
    def _cn_num(n: int) -> str:
        cn = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        if 0 <= n <= 10:
            return cn[n]
        if n < 20:
            return f"十{cn[n - 10]}"
        if n < 100:
            tail = cn[n % 10] if n % 10 else ""
            return f"{cn[n // 10]}十{tail}"
        return str(n)

    @staticmethod
    def _query_priority(q: str, queries: list) -> int:
        # docstring removed after encoding cleanup
        try:
            return queries.index(q)
        except ValueError:
            return 999

    @staticmethod
    def _season_title_bonus(season_title: str, candidate: dict) -> float:
        value = str(season_title or "").strip().lower()
        if not value:
            return 0.0
        candidate_title = str(candidate.get("title", "") or "").strip().lower()
        if not candidate_title:
            return 0.0
        if value == candidate_title:
            return 35.0
        if value in candidate_title:
            return 28.0
        tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", value))
        candidate_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", candidate_title))
        if not tokens or not candidate_tokens:
            return 0.0
        overlap = len(tokens & candidate_tokens) / max(len(tokens), 1)
        return round(22 * overlap, 2)

    @staticmethod
    def _chapter_title_bonus(chapter_name: str, part: int | None, candidate: dict) -> float:
        chapter = str(chapter_name or "").strip().lower()
        candidate_title = str(candidate.get("title", "") or "").strip().lower()
        if not candidate_title:
            return 0.0
        bonus = 0.0
        if chapter:
            if chapter in candidate_title:
                bonus += 32.0
            else:
                tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", chapter))
                candidate_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", candidate_title))
                if tokens and candidate_tokens:
                    bonus += round(24 * (len(tokens & candidate_tokens) / max(len(tokens), 1)), 2)
        if part and part > 0:
            part_num = int(part)
            if re.search(rf"(?:part|#)\s*{part_num}\b", candidate_title, re.IGNORECASE):
                bonus += 18.0
            elif chapter and re.search(rf"{re.escape(chapter)}\s*{part_num}\b", candidate_title, re.IGNORECASE):
                bonus += 18.0
            elif re.search(rf"(?<!\d){part_num}(?!\d)", candidate_title):
                bonus += 8.0
        return bonus

    @classmethod
    def _candidate_matches_detail(cls, season_title: str, chapter_name: str, part: int | None, candidate: dict) -> bool:
        candidate_title = str(candidate.get("title", "") or "").strip().lower()
        if not candidate_title:
            return False
        detail = str(chapter_name or "").strip().lower() or str(season_title or "").strip().lower()
        if detail:
            candidate_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", candidate_title))
            detail_variants = [detail]
            trimmed_detail = re.sub(r"[篇章]$", "", detail).strip()
            if trimmed_detail and trimmed_detail != detail:
                detail_variants.append(trimmed_detail)
            matched_detail = False
            for variant in detail_variants:
                detail_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", variant))
                if variant in candidate_title or (detail_tokens and detail_tokens <= candidate_tokens):
                    matched_detail = True
                    break
            if not matched_detail:
                return False
        if part and int(part) > 0:
            part_num = int(part)
            if part_num == 1 and detail:
                explicit_part = re.search(r"(?:part|#)\s*(\d{1,2})\b", candidate_title, re.IGNORECASE)
                if explicit_part and int(explicit_part.group(1)) != part_num:
                    return False
                detail_part = re.search(rf"{re.escape(detail)}\s*#?\s*(\d{{1,2}})\b", candidate_title, re.IGNORECASE)
                if detail_part and int(detail_part.group(1)) != part_num:
                    return False
                return True
            if re.search(rf"(?:part|#)\s*{part_num}\b", candidate_title, re.IGNORECASE):
                return True
            if detail and re.search(rf"{re.escape(detail)}\s*#?\s*{part_num}\b", candidate_title, re.IGNORECASE):
                return True
            if re.search(rf"(?<!\d){part_num}(?!\d)", candidate_title):
                return True
            return False
        return True

    @classmethod
    def _metadata_matches_detail(cls, season_title: str, chapter_name: str, part: int | None, metadata: dict) -> bool:
        if not chapter_name and not part:
            return True
        title = str(metadata.get("title") or "").strip()
        meta_season_title = str(metadata.get("season_title") or "").strip()
        combined_title = " ".join(value for value in [title, meta_season_title] if value).strip()
        return cls._candidate_matches_detail(season_title, chapter_name, part, {"title": combined_title})

    def _score_candidate(self, target_title: str, target_season: int, target_year: int, candidate: dict) -> float:
        # docstring removed after encoding cleanup
        candidate_title = str(candidate.get("title", "").strip()).lower()
        target_title_lower = target_title.lower()
        
        title_score = 0.0
        
        # 鏍囬鍖归厤
        if target_title_lower == candidate_title:
            title_score = 70
        elif target_title_lower in candidate_title or candidate_title in target_title_lower:
            title_score = 54
        else:
            target_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", target_title_lower))
            candidate_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", candidate_title))
            if target_tokens and candidate_tokens:
                title_score = 45 * (len(target_tokens & candidate_tokens) / max(len(target_tokens | candidate_tokens), 1))
        if title_score <= 0:
            return -30.0

        score = title_score
        
        # 瀛暟鍖归厤
        candidate_season = self._extract_season(candidate_title)
        if target_season:
            if candidate_season == target_season:
                score += 26
            elif candidate_season is not None:
                score -= min(18, abs(candidate_season - target_season) * 8)
        
        # 骞翠唤鍖归厤
        if target_year:
            candidate_year = self._extract_year(candidate_title)
            if candidate_year:
                gap = abs(target_year - candidate_year)
                score += max(0, 20 - min(gap, 20))
        
        return round(score, 2)

    def _extract_season(self, text: str) -> int | None:
        # docstring removed after encoding cleanup
        match = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*季", text, re.IGNORECASE)
        if match:
            season_token = match.group(1)
            if season_token.isdigit():
                return int(season_token)
            cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            return cn_map.get(season_token)

        match = re.search(r"\bS(\d{1,2})\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        match = re.search(r"Season\s*(\d{1,2})", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return None
    def _extract_year(self, text: str) -> int | None:
        # docstring removed after encoding cleanup
        match = re.search(r"(\d{4})", text)
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2035:
                return year
        return None

    def _search_anibk(self, query: str) -> list:
        # docstring removed after encoding cleanup
        try:
            url = f"{ANIBK_SEARCH}{quote(query)}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            soup = BeautifulSoup(resp.text, "html.parser")
            candidates = []
            seen = set()

            for a in soup.find_all("a", href=True):
                href = a["href"]
                # AniBK 璇儏椤垫牸寮? /bk/12345
                if href.startswith("/bk/") and href.split("/")[-1].isdigit():
                    title_text = a.get_text(strip=True)
                    full_url = urljoin(ANIBK_BASE, href)
                    if title_text and full_url not in seen:
                        seen.add(full_url)
                        candidates.append({"title": title_text, "url": full_url})

            return candidates
        except Exception as e:
            logger.warning("AniBK 搜索失败: %s", e)
            return []

    @staticmethod
    def _extract_douban_info_values(info_text: str, label: str) -> list[str]:
        lines = [line.strip() for line in str(info_text or "").splitlines() if line.strip()]
        for index, line in enumerate(lines):
            normalized = line.replace("：", ":")
            if not normalized.startswith(label):
                continue
            raw = normalized[len(label):].lstrip(":").strip()
            if not raw and index + 1 < len(lines):
                values = []
                for next_line in lines[index + 1:]:
                    next_normalized = next_line.replace("：", ":")
                    if next_normalized.endswith(":") or re.match(r"^[\u4e00-\u9fffA-Za-z /]+:$", next_normalized):
                        break
                    if next_line == "/":
                        continue
                    values.append(next_line)
                    if len(values) >= 4:
                        break
                raw = " / ".join(values)
            if raw:
                return [part.strip() for part in re.split(r"/|,|，", raw) if part.strip()]
        return []

    def _scrape_douban(self, title: str, year: int = 0, season: int = 1, chapter_name: str = "", part: int | None = None) -> dict:
        result = self._empty_result(year)
        if not self.config.DOUBAN_COOKIE:
            return result
        try:
            candidates = self._search_douban_candidates(title, year, season)
            if not candidates:
                logger.debug("豆瓣无搜索结果")
                return result

            candidates.sort(key=lambda item: item.get("match_score", 0), reverse=True)
            return self._scrape_douban_detail(candidates[0]["url"], title, year, season, candidates[0].get("match_score", 0), chapter_name, part)
        except Exception as e:
            logger.warning("豆瓣刮削失败: %s", e)
            return result

    def _search_douban_candidates(self, title: str, year: int = 0, season: int = 1) -> list[dict]:
        candidates: list[dict] = []
        seen = set()

        try:
            suggest_url = f"{DOUBAN_BASE}/j/subject_suggest?q={quote(title)}"
            resp = self._douban_get(suggest_url, ajax=True)
            resp.raise_for_status()
            for item in resp.json()[:10]:
                item_title = str(item.get("title") or "").strip()
                detail_url = str(item.get("url") or "").strip().split("?", 1)[0].rstrip("/")
                if not item_title or not detail_url or detail_url in seen:
                    continue
                seen.add(detail_url)
                try:
                    item_year = int(str(item.get("year") or "0")[:4] or 0)
                except (TypeError, ValueError):
                    item_year = 0
                candidates.append({
                    "title": item_title,
                    "url": detail_url,
                    "year": item_year,
                    "match_score": self._score_candidate(title, season, year or item_year, {"title": item_title, "year": item_year}),
                })
        except HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 0
            if status_code in {403, 404, 410}:
                logger.debug("豆瓣 suggest 不可用，降级到页面搜索: HTTP %s title=%s", status_code, title)
            else:
                logger.debug("豆瓣 suggest 搜索失败，降级到页面搜索: %s", exc)
        except Exception as exc:
            logger.debug("豆瓣 suggest 搜索失败，降级到页面搜索: %s", exc)

        if candidates:
            return candidates

        try:
            for search_url in (
                f"{DOUBAN_BASE}/search?q={quote(title)}",
                f"https://www.douban.com/search?cat=1002&q={quote(title)}",
            ):
                resp = self._douban_get(search_url)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("a", href=re.compile(r"https?://movie\.douban\.com/subject/\d+")):
                    href = link.get("href", "").split("?", 1)[0].rstrip("/")
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    text = link.get_text(" ", strip=True)
                    parent = link.find_parent()
                    parent_text = parent.get_text(" ", strip=True) if parent else ""
                    display_title = (text or parent_text or title)[:180]
                    item_year = self._extract_year(parent_text) or 0
                    candidates.append({
                        "title": display_title,
                        "url": href,
                        "year": item_year,
                        "match_score": self._score_candidate(title, season, year or item_year, {"title": display_title, "year": item_year}),
                    })
                if candidates:
                    break
        except Exception as exc:
            logger.warning("豆瓣页面搜索失败: %s", exc)
        return candidates

    def _scrape_douban_detail(self, detail_url: str, title: str, year: int, season: int, score: float, chapter_name: str = "", part: int | None = None) -> dict:
        result = self._empty_result(year)
        result["match_score"] = score
        result["metadata_source"] = "douban"
        try:
            resp = self._douban_get(detail_url)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.find("span", property="v:itemreviewed") or soup.find("meta", property="og:title")
            if title_el:
                result["title"] = title_el.get_text(" ", strip=True) if title_el.name != "meta" else title_el.get("content", "")
            if not result["title"]:
                result["title"] = title

            year_el = soup.find("span", class_="year")
            if year_el:
                match = re.search(r"\d{4}", year_el.get_text())
                if match:
                    result["year"] = int(match.group(0))

            rating_el = soup.find("strong", property="v:average") or soup.find("strong", class_="ll rating_num")
            if rating_el:
                try:
                    result["score"] = float(rating_el.get_text(strip=True))
                except ValueError:
                    pass

            desc_el = soup.find("span", property="v:summary") or soup.find("meta", property="og:description")
            if desc_el:
                desc = desc_el.get_text(" ", strip=True) if desc_el.name != "meta" else desc_el.get("content", "")
                result["description"] = re.sub(r"\s+", " ", desc).strip()[:500]

            tags = []
            for genre in soup.find_all("span", property="v:genre"):
                text = genre.get_text(strip=True)
                if text:
                    tags.append(text)
            result["genres"] = tags[:8]

            info_el = soup.find(id="info")
            if info_el:
                info_text = info_el.get_text("\n", strip=True)
                countries = self._extract_douban_info_values(info_text, "制片国家/地区")
                duration = (
                    self._extract_douban_info_values(info_text, "片长")
                    or self._extract_douban_info_values(info_text, "单集片长")
                )
                result["countries"] = countries[:4]
                if duration:
                    result["duration"] = duration[0]
            result["tags"] = list(dict.fromkeys(result["genres"] + result["countries"]))

            image_el = soup.find("meta", property="og:image") or soup.find("img", rel="v:image")
            image_url = image_el.get("content") if image_el and image_el.name == "meta" else (image_el.get("src") if image_el else "")
            if image_url:
                local_cover = self._download_cover(image_url, title, season, chapter_name, part)
                result["cover_url"] = local_cover or image_url
                result["backdrop_url"] = result["cover_url"]

            result["douban_url"] = detail_url
            return result
        except Exception as e:
            logger.warning("豆瓣详情刮削失败: %s", e)
            return result

    def _scrape_tmdb_api(
        self,
        title: str,
        year: int = 0,
        season: int = 1,
        category: str = "",
        season_title: str = "",
        aliases: list[str] | None = None,
        origin_countries: list[str] | None = None,
        chapter_name: str = "",
        part: int | None = None,
    ) -> dict:
        result = self._empty_result(year)
        api_key = str(self.config.TMDB_API_KEY or "").strip()
        if not api_key:
            return result
        try:
            base = str(self.config.TMDB_API_BASE or "https://api.themoviedb.org/3").rstrip("/")
            queries = self._tmdb_search_queries(title, aliases, category)
            allowed_media_types = self._tmdb_allowed_media_types(category)
            items = []
            for index, query in enumerate(queries):
                resp = self.session.get(
                    f"{base}/search/multi",
                    params={"api_key": api_key, "query": query, "language": "zh-CN", "include_adult": "false"},
                    timeout=12,
                )
                resp.raise_for_status()
                for item in resp.json().get("results", []) or []:
                    if item.get("media_type") not in {"movie", "tv"}:
                        continue
                    if allowed_media_types and item.get("media_type") not in allowed_media_types:
                        continue
                    item["_query"] = query
                    item["_query_index"] = index
                    items.append(item)
            if not items:
                logger.debug("TMDB API search returned no result")
                return result

            def score_item(item: dict) -> float:
                item_title = item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name") or ""
                item_year = self._extract_year(item.get("release_date") or item.get("first_air_date") or "")
                query = item.get("_query") or title
                candidate_titles = self._tmdb_candidate_titles(item)
                score = max(
                    self._score_candidate(target, season, year, {"title": candidate_title})
                    for target in (title, query)
                    for candidate_title in candidate_titles
                )
                score += max(0, 12 - int(item.get("_query_index") or 0) * 2)
                if year and item_year == year:
                    score += 15
                score += self._tmdb_category_bonus(item, category, origin_countries)
                return score

            items.sort(key=score_item, reverse=True)
            best = items[0]
            media_type = best.get("media_type")
            tmdb_id = best.get("id")
            details = self._fetch_tmdb_details(base, api_key, media_type, tmdb_id)
            season_details = self._fetch_tmdb_season_details(base, api_key, media_type, tmdb_id, season)
            found_title = best.get("title") or best.get("name") or title
            result["title"] = found_title
            result["original_title"] = best.get("original_title") or best.get("original_name") or ""
            result["description"] = translate_to_chinese(((details.get("overview") or best.get("overview") or "")[:500]))
            result["score"] = round(float(details.get("vote_average") or best.get("vote_average") or 0), 1)
            result["vote_count"] = int(details.get("vote_count") or best.get("vote_count") or 0)
            found_year = self._extract_year(
                details.get("release_date") or details.get("first_air_date") or best.get("release_date") or best.get("first_air_date") or ""
            )
            if found_year:
                result["year"] = found_year

            poster = season_details.get("poster_path") or details.get("poster_path") or best.get("poster_path")
            if poster:
                local_cover = self._download_cover(self._tmdb_image_url(poster, "poster"), title, season, chapter_name, part)
                if local_cover:
                    result["cover_url"] = local_cover

            backdrop = self._tmdb_season_backdrop(season_details) or details.get("backdrop_path") or best.get("backdrop_path")
            if backdrop:
                local_backdrop = self._download_cover(self._tmdb_image_url(backdrop, "backdrop"), title, season, chapter_name, part)
                if local_backdrop:
                    result["backdrop_url"] = local_backdrop
            elif result.get("cover_url"):
                result["backdrop_url"] = result["cover_url"]

            result["genres"] = [item.get("name", "") for item in details.get("genres", []) if item.get("name")]
            result["countries"] = self._tmdb_countries(details, best)
            result["languages"] = self._tmdb_languages(details, best)
            result["tags"] = list(dict.fromkeys(result["genres"] + result["countries"]))
            result["duration"] = self._tmdb_duration(details, media_type)
            result["season_tmdb_id"] = season_details.get("id") or ""
            result["season_title"] = season_title or season_details.get("name") or ""
            result["tmdb_id"] = tmdb_id
            result["tmdb_media_type"] = media_type
            result["metadata_source"] = "tmdb"
            return result
        except Exception as e:
            logger.warning("TMDB API 刮削失败: %s", e)
            return result

    def _fetch_tmdb_details(self, base: str, api_key: str, media_type: str, tmdb_id) -> dict:
        if media_type not in {"movie", "tv"} or not tmdb_id:
            return {}
        try:
            resp = self.session.get(
                f"{base}/{media_type}/{tmdb_id}",
                params={"api_key": api_key, "language": "zh-CN"},
                timeout=12,
            )
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as exc:
            logger.warning("TMDB 详情获取失败: %s", exc)
            return {}

    def _fetch_tmdb_season_details(self, base: str, api_key: str, media_type: str, tmdb_id, season: int) -> dict:
        if media_type != "tv" or not tmdb_id or not season:
            return {}
        try:
            resp = self.session.get(
                f"{base}/tv/{tmdb_id}/season/{int(season)}",
                params={"api_key": api_key, "language": "zh-CN"},
                timeout=12,
            )
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as exc:
            logger.warning("TMDB 季详情获取失败: %s", exc)
            return {}

    @staticmethod
    def _tmdb_season_backdrop(season_details: dict) -> str:
        episodes = season_details.get("episodes") or []
        for episode in episodes:
            still = str(episode.get("still_path") or "").strip()
            if still:
                return still
        return ""

    def _tmdb_allowed_media_types(self, category: str) -> set[str]:
        kind = self._category_kind(category)
        if kind == "movie":
            return {"movie"}
        return {"tv"}

    @staticmethod
    def _tmdb_candidate_titles(item: dict) -> list[str]:
        titles = [
            item.get("title"),
            item.get("name"),
            item.get("original_title"),
            item.get("original_name"),
        ]
        return list(dict.fromkeys([str(title or "").strip() for title in titles if str(title or "").strip()])) or [""]

    def _tmdb_category_bonus(self, item: dict, category: str, origin_countries: list[str] | None = None) -> float:
        kind = self._category_kind(category)
        media_type = str(item.get("media_type") or "").strip().lower()
        bonus = 0.0

        if kind == "movie":
            bonus += 10.0 if media_type == "movie" else -8.0
        else:
            bonus += 10.0 if media_type == "tv" else -6.0

        item_country_codes = {str(code or "").upper() for code in (item.get("origin_country") or []) if code}
        if kind == "anime":
            if "JP" in item_country_codes:
                bonus += 8.0
            elif item_country_codes:
                bonus -= 3.0

        requested = {str(value or "").strip().upper() for value in (origin_countries or []) if str(value or "").strip()}
        if requested and item_country_codes:
            mapped_names = {
                str(COUNTRY_NAME_MAP.get(code, code)).strip().upper()
                for code in item_country_codes
            }
            if requested & item_country_codes or requested & mapped_names:
                bonus += 6.0

        popularity = float(item.get("popularity") or 0)
        if popularity > 0:
            bonus += min(4.0, popularity / 40.0)
        return bonus

    def _tmdb_search_queries(self, title: str, aliases: list[str] | None, category: str) -> list[str]:
        title_query = str(title or "").strip()
        alias_queries = [str(alias or "").strip() for alias in aliases or []]
        queries = []
        if self._category_kind(category) == "anime":
            queries.extend(alias_queries)
            queries.extend(self._anime_builtin_aliases(title))
            translated = self._translate_query_for_region(title, "ja")
            if translated:
                queries.append(translated)
            queries.append(title_query)
        else:
            queries.append(title_query)
            queries.extend(alias_queries)
        return list(dict.fromkeys([query for query in queries if query]))

    @staticmethod
    def _translate_query_for_region(title: str, region: str) -> str:
        value = str(title or "").strip()
        if not value or region != "ja":
            return ""
        alias_map = {
            "石纪元": "Dr. Stone",
            "葬送的芙莉莲": "Frieren: Beyond Journey's End",
            "电锯人": "Chainsaw Man",
            "进击的巨人": "Attack on Titan",
            "鬼灭之刃": "Demon Slayer",
            "咒术回战": "Jujutsu Kaisen",
        }
        for key, alias in alias_map.items():
            if key in value:
                return alias
        return ""

    @staticmethod
    def _anime_builtin_aliases(title: str) -> list[str]:
        mapping = {
            "Charlotte": ["シャーロット"],
            "Dr. Stone": ["ドクターストーン"],
            "Frieren": ["Frieren: Beyond Journey's End", "葬送のフリーレン"],
            "Chainsaw Man": ["チェンソーマン"],
        }
        result = []
        source_title = str(title or "").strip().lower()
        for key, values in mapping.items():
            if key.lower() == source_title or key.lower() in source_title:
                result.extend(values)
        return result
    @staticmethod
    def _tmdb_countries(details: dict, item: dict) -> list[str]:
        values = []
        for country in details.get("production_countries", []) or []:
            name = country.get("name") or COUNTRY_NAME_MAP.get(country.get("iso_3166_1", ""), "")
            if name:
                values.append(name)
        for code in details.get("origin_country", []) or item.get("origin_country", []) or []:
            values.append(COUNTRY_NAME_MAP.get(str(code).upper(), str(code).upper()))
        return list(dict.fromkeys(values))

    @staticmethod
    def _tmdb_languages(details: dict, item: dict) -> list[str]:
        values = []
        for language in details.get("spoken_languages", []) or []:
            name = language.get("name") or language.get("english_name")
            if name:
                values.append(name)
        original = details.get("original_language") or item.get("original_language")
        if original:
            values.append(str(original).upper())
        return list(dict.fromkeys(values))

    @staticmethod
    def _tmdb_duration(details: dict, media_type: str) -> str:
        if media_type == "movie":
            runtime = int(details.get("runtime") or 0)
            return f"{runtime} 分钟" if runtime else ""
        runtimes = details.get("episode_run_time") or []
        runtime = int(runtimes[0]) if runtimes else 0
        return f"{runtime} 分钟/集" if runtime else ""

    def _tmdb_image_url(self, image_path: str, image_type: str = "poster") -> str:
        path = str(image_path or "").strip()
        if not path:
            return ""
        if path.startswith(("http://", "https://")):
            return path
        base = str(self.config.TMDB_IMAGE_BASE or TMDB_IMG_BASE).rstrip("/")
        if image_type == "backdrop":
            base = TMDB_BACKDROP_BASE
        return f"{base}/{path.lstrip('/')}"

    def _scrape_tmdb_web(self, title: str, year: int = 0, chapter_name: str = "", part: int | None = None) -> dict:
        # docstring removed after encoding cleanup
        result = self._empty_result(year)
        result["metadata_source"] = "tmdb-web"
        try:
            search_url = f"{TMDB_BASE}/search?query={quote(title)}"
            resp = self.session.get(search_url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            soup = BeautifulSoup(resp.text, "html.parser")
            card = self._find_tmdb_best_card(soup, title, year)
            if not card:
                logger.debug("TMDB web search returned no result")
                return result

            title_link = card.find("a", href=re.compile(r"^/(movie|tv)/"))
            h2 = card.find("h2")
            found_title = h2.get_text(" ", strip=True) if h2 else title
            found_title = re.sub(r"\s+", " ", found_title).strip()
            result["title"] = found_title or title

            release_el = card.find(class_=re.compile(r"release_date"))
            release_text = release_el.get_text(" ", strip=True) if release_el else ""
            year_match = re.search(r"(19\d{2}|20\d{2}|21\d{2})", release_text)
            if year_match:
                result["year"] = int(year_match.group(1))

            desc_el = card.find("p")
            if desc_el:
                result["description"] = translate_to_chinese(desc_el.get_text(" ", strip=True)[:500])

            image_url = self._extract_tmdb_card_image(card)
            if image_url:
                local_cover = self._download_cover(image_url, title, 1, chapter_name, part)
                if local_cover:
                    result["cover_url"] = local_cover
                    result["backdrop_url"] = local_cover

            result["match_score"] = self._score_candidate(title, 1, year, {"title": found_title})
            if title_link:
                result["tmdb_url"] = urljoin(TMDB_BASE, title_link.get("href", ""))
            return result
        except Exception as e:
            logger.warning("TMDB 网页刮削失败: %s", e)
            return result

    def _find_tmdb_best_card(self, soup: BeautifulSoup, title: str, year: int = 0):
        cards = []
        for link in soup.find_all("a", href=re.compile(r"^/(movie|tv)/")):
            card = link.find_parent(
                lambda tag: tag.name == "div"
                and tag.get("class")
                and any("media-card" in str(cls) for cls in tag.get("class", []))
            )
            if card and card not in cards:
                cards.append(card)
        if not cards:
            return None

        def score(card) -> float:
            h2 = card.find("h2")
            card_title = h2.get_text(" ", strip=True) if h2 else card.get_text(" ", strip=True)[:80]
            base = self._score_candidate(title, 1, year, {"title": card_title})
            if year:
                release_el = card.find(class_=re.compile(r"release_date"))
                release_text = release_el.get_text(" ", strip=True) if release_el else ""
                if str(year) in release_text:
                    base += 20
            return base

        cards.sort(key=score, reverse=True)
        return cards[0]

    @staticmethod
    def _extract_tmdb_card_image(card) -> str:
        img = card.find("img")
        if not img:
            return ""
        srcset = img.get("srcset") or ""
        if srcset:
            parts = [part.strip().split(" ")[0] for part in srcset.split(",") if part.strip()]
            if parts:
                return parts[-1]
        return img.get("src") or ""

    def _get_anibk_cover(self, detail_url: str) -> str:
        # docstring removed after encoding cleanup
        try:
            headers = HEADERS.copy()
            headers["Referer"] = ANIBK_BASE
            resp = self.session.get(detail_url, headers=headers, timeout=10)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            soup = BeautifulSoup(resp.text, "html.parser")
            # 鏌壘灏侀潰瀹瑰櫒
            cover_box = soup.find("div", class_="bk-main-pic") or soup.find("div", class_="rbox-pic")
            if cover_box:
                img = cover_box.find("img", src=True)
                if img and img["src"]:
                    return img["src"]

            return ""
        except Exception as e:
            logger.warning("提取封面失败: %s", e)
            return ""

    def _get_anibk_intro(self, detail_url: str) -> str:
        # docstring removed after encoding cleanup
        try:
            headers = HEADERS.copy()
            headers["Referer"] = ANIBK_BASE
            resp = self.session.get(detail_url, headers=headers, timeout=10)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            soup = BeautifulSoup(resp.text, "html.parser")
            intro_container = soup.find("div", class_="bkir-content")
            if not intro_container:
                return ""

            paragraphs = []
            for p in intro_container.find_all("p"):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)

            intro = "".join(paragraphs)
            return translate_to_chinese(intro)
        except Exception as e:
            logger.warning("提取简介失败: %s", e)
            return ""

    def _get_anibk_year(self, detail_url: str) -> int:
        # docstring removed after encoding cleanup
        try:
            headers = HEADERS.copy()
            headers["Referer"] = ANIBK_BASE
            resp = self.session.get(detail_url, headers=headers, timeout=10)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            soup = BeautifulSoup(resp.text, "html.parser")
            page_text = soup.get_text()

            # 1. "涓婃槧鏃堕棿|鍙戣鏃堕棿|棣栨挱鏃堕棿|鎾嚭鏃堕棿" 鍚庣殑骞翠唤
            date_match = re.search(r"(涓婃槧鏃堕棿|鍙戣鏃堕棿|棣栨挱鏃堕棿|鎾嚭鏃堕棿)\s*[锛?]\s*(\d{4})", page_text)
            if date_match:
                return int(date_match.group(2))

            # 2. YYYY-MM-DD 鏍煎紡
            full_date = re.search(r"(\d{4})-\d{2}-\d{2}", page_text)
            if full_date:
                return int(full_date.group(1))

            # 3. 鏍囬涓殑骞翠唤
            title_elem = soup.find("h1", class_="bk-title") or soup.find("h1")
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                title_year_match = re.search(r'[(（](\d{4})[)）]', title_text)
                if title_year_match:
                    return int(title_year_match.group(1))

            # 4. YYYY year format
            year_cn = re.search(r"(\d{4})年", page_text)
            if year_cn:
                y = int(year_cn.group(1))
                if 1900 <= y <= 2030:
                    return y

            all_years = re.findall(r"(\d{4})", page_text)
            for y_str in all_years:
                y = int(y_str)
                if 1900 <= y <= 2030:
                    return y

            return 0
        except Exception as e:
            logger.warning("提取年份失败: %s", e)
            return 0

    def _download_cover(self, image_url: str, title: str, season: int = 1, chapter_name: str = "", part: int | None = None) -> str:
        # Download a cover image to covers/ and return the local URL.
        try:
            if not image_url:
                return ""

            safe_title = re.sub(r"[^\w\u4e00-\u9fff]", "_", title)[:30]
            file_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            
            season_suffix = f"_S{season}" if season > 1 else ""
            
            safe_chapter = re.sub(r"[^\w\u4e00-\u9fff]", "_", chapter_name)[:10] if chapter_name else ""
            chapter_suffix = f"_{safe_chapter}" if safe_chapter else ""
            
            part_suffix = f"_P{part}" if part and part > 0 else ""
            
            filename = f"{safe_title}{season_suffix}{chapter_suffix}{part_suffix}_{file_hash}.webp"
            filepath = COVERS_DIR / filename
            if filepath.exists():
                return f"/covers/{quote(filename)}"

            headers = HEADERS.copy()
            if ANIBK_BASE in image_url:
                headers["Referer"] = ANIBK_BASE
            elif "doubanio.com" in image_url or "douban.com" in image_url:
                headers["Referer"] = DOUBAN_BASE
            else:
                headers["Referer"] = TMDB_BASE

            resp = self.session.get(image_url, headers=headers, timeout=15, stream=True)
            resp.raise_for_status()
            content_type = (resp.headers.get("content-type") or "").lower()
            if not content_type.startswith("image/"):
                logger.warning("Cover response is not an image: %s (%s)", image_url, content_type or "unknown")
                return ""

            img_suffix = "jpg"
            if "image/webp" in content_type or ".webp" in image_url.lower():
                img_suffix = "webp"
            elif "image/png" in content_type or ".png" in image_url.lower():
                img_suffix = "png"

            filename = f"{safe_title}{season_suffix}{chapter_suffix}{part_suffix}_{file_hash}.{img_suffix}"
            filepath = COVERS_DIR / filename
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 8):
                    f.write(chunk)

            logger.debug("Cover downloaded: %s", filename)
            return f"/covers/{quote(filename)}"
        except Exception as e:
            logger.warning("Cover download failed [%s]: %s", title, e)
            return ""

