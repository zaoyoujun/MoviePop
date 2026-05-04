from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(tags=["library"])


def _get_services():
    from backend.app import library_service, scraper_service, job_manager
    return library_service, scraper_service, job_manager


@router.get("/api/library")
def get_library(
    mode: str = Query(default="all"),
    source: str = Query(default="remote"),
    search: str = Query(default=""),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    library_service, _, _ = _get_services()
    movies = library_service.get_movies(
        mode=mode, source=source, search=search, force_refresh=force_refresh,
    )
    return {"items": movies, "stats": library_service.get_stats()}


@router.post("/api/library/refresh")
def refresh_library(
    source: str = Query(default="remote"),
    auto_scrape: bool = Query(default=True),
) -> dict[str, str]:
    library_service, scraper_service, job_manager = _get_services()

    def task(update):
        if source == "combined":
            movie_count = 0
            scrape_total = 0
            scrape_updated = 0
            for index, current_source in enumerate(("remote", "local"), start=1):
                update(index - 1, 2, f"Refreshing {current_source} library")
                movies = library_service.refresh_library(source=current_source)
                movie_count += len(movies)
                if auto_scrape and movies:
                    scrape_result = scraper_service.scrape_library(source=current_source, progress=update)
                    scrape_total += scrape_result.get("total", 0)
                    scrape_updated += scrape_result.get("updated", 0)
            return {
                "movie_count": movie_count,
                "scrape": {"total": scrape_total, "updated": scrape_updated},
                "source": source,
            }

        scan_target = "本地目录" if source == "local" else "WebDAV 目录"
        update(0, 1, f"正在扫描{scan_target}")
        movies = library_service.refresh_library(source=source)
        if auto_scrape and movies:
            update(0, len(movies), "扫描完成，开始补全封面和简介")
            scrape_result = scraper_service.scrape_library(source=source, progress=update)
        else:
            scrape_result = {"total": len(movies), "updated": 0}
        return {"movie_count": len(movies), "scrape": scrape_result, "source": source}

    job = job_manager.start(f"refresh-{source}-library", task)
    return {"job_id": job.job_id}


@router.post("/api/library/scrape")
def scrape_library(source: str = Query(default="remote")) -> dict[str, str]:
    _, scraper_service, job_manager = _get_services()

    def task(update):
        if source != "combined":
            return scraper_service.scrape_library(source=source, progress=update)

        total = 0
        updated = 0
        for index, current_source in enumerate(("remote", "local"), start=1):
            update(index - 1, 2, f"Scraping {current_source} metadata")
            result = scraper_service.scrape_library(source=current_source, progress=update)
            total += result.get("total", 0)
            updated += result.get("updated", 0)
        return {"total": total, "updated": updated, "source": source}

    job = job_manager.start(f"scrape-{source}-library", task)
    return {"job_id": job.job_id}
