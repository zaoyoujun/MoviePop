from __future__ import annotations

from typing import Any, Callable

from core.cover_scraper import CoverScraper
from utils.logger import get_logger

logger = get_logger()

ProgressCallback = Callable[[int, int, str], None]


class ScraperService:
    def __init__(self, library_service) -> None:
        self.library_service = library_service
        self.scraper = CoverScraper()

    def search_candidates(self, movie_path: str, custom_name: str | None = None) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        candidates = self.scraper.search_candidates(movie, custom_name=custom_name)
        serialized: list[dict[str, Any]] = []
        for item in candidates:
            year = item.get("year")
            if not isinstance(year, int) or not 1900 <= year <= 2030:
                year = None
            serialized.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "year": year,
                    "match_score": item.get("match_score"),
                    "matched_query": item.get("matched_query", ""),
                    "strategy_source": item.get("strategy_source", ""),
                }
            )
        diagnostics: list[dict[str, Any]] = []
        for item in getattr(self.scraper, "_last_candidate_diagnostics", []) or []:
            diagnostics.append(
                {
                    "source": item.get("source", ""),
                    "queries": int(item.get("queries") or 0),
                    "hits": int(item.get("hits") or 0),
                    "status": item.get("status", "idle"),
                    "error": str(item.get("error") or "").strip(),
                }
            )
        return {"items": serialized, "diagnostics": diagnostics}

    def apply_candidate(self, movie_path: str, candidate: dict[str, Any]) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        candidate_payload = dict(candidate)
        if candidate_payload.get("source") == "TMDB":
            candidate_payload["parse_func"] = self.scraper._get_tmdb_cover  # noqa: SLF001
        elif candidate_payload.get("source") == "Douban":
            candidate_payload["parse_func"] = self.scraper._get_douban_cover  # noqa: SLF001
        else:
            candidate_payload["parse_func"] = self.scraper._get_anibk_cover  # noqa: SLF001

        cover_path, intro_text, scraped_year = self.scraper.download_by_candidate(candidate_payload, movie)
        updates: dict[str, Any] = {}
        if cover_path:
            updates["cover_path"] = cover_path
        if candidate_payload.get("title"):
            updates["title"] = candidate_payload["title"]
            updates["name"] = candidate_payload["title"]
        if intro_text and intro_text.strip():
            updates["intro"] = intro_text.strip()
        if scraped_year:
            updates["year"] = scraped_year
        elif isinstance(candidate_payload.get("year"), int) and 1900 <= candidate_payload["year"] <= 2030:
            updates["year"] = candidate_payload["year"]

        if not updates:
            raise ValueError("未能从所选结果中更新任何信息")
        return self.library_service.save_custom_info(movie_path, updates, source=movie.get("source"))

    def scrape_single(self, movie_path: str, custom_name: str | None = None) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        cover_path, intro_text, scraped_year = self.scraper.search_cover(
            movie, custom_name=custom_name, force_update_meta=True,
        )
        updates: dict[str, Any] = {}
        if cover_path:
            updates["cover_path"] = cover_path
        if intro_text and intro_text.strip():
            updates["intro"] = intro_text.strip()
        if scraped_year:
            updates["year"] = scraped_year
        if not updates:
            raise ValueError("没有获取到新的封面或元数据")
        return self.library_service.update_library_fields(movie_path, updates, source=movie.get("source"))

    def scrape_library(self, source: str = "remote", progress: ProgressCallback | None = None) -> dict[str, Any]:
        raw_movies = self.library_service._load_raw_library(source, force_refresh=False)  # noqa: SLF001
        total = len(raw_movies)
        updated_count = 0
        for index, movie in enumerate(raw_movies, start=1):
            title = movie.get("title") or movie.get("name") or "未命名"
            if progress:
                progress(index - 1, total, f"正在补全《{title}》")
            try:
                cover_path, intro_text, scraped_year = self.scraper.search_cover(
                    movie, force_update_meta=True,
                )
            except Exception:
                logger.exception("刮削失败: %s", title)
                continue
            if cover_path:
                movie["cover_path"] = cover_path
            if intro_text and intro_text.strip():
                movie["intro"] = intro_text.strip()
            if scraped_year:
                movie["year"] = scraped_year
            if cover_path or (intro_text and intro_text.strip()) or scraped_year:
                updated_count += 1

        self.library_service._save_raw_library(source, raw_movies)  # noqa: SLF001
        if progress:
            progress(total, total, "元数据补全完成")
        return {"total": total, "updated": updated_count}
