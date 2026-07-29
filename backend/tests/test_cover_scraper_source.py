import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.cover_scraper import CoverScraper


def _scraper_with_source(source):
    scraper = CoverScraper.__new__(CoverScraper)
    scraper.config = SimpleNamespace(SCRAPE_SOURCE=source, DOUBAN_COOKIE="")
    return scraper


def test_selected_scraper_source_does_not_query_other_providers_after_success(monkeypatch):
    scraper = _scraper_with_source("tmdb")
    calls = []

    monkeypatch.setattr(
        scraper,
        "_scrape_tmdb",
        lambda *args: calls.append("tmdb") or {"title": "Example", "cover_url": "poster"},
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_anibk",
        lambda *args: (_ for _ in ()).throw(AssertionError("unexpected AniBK request")),
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_douban",
        lambda *args: (_ for _ in ()).throw(AssertionError("unexpected Douban request")),
    )

    result = scraper.scrape("Example", category="series")

    assert calls == ["tmdb"]
    assert result["title"] == "Example"
    assert result["backdrop_url"] == "poster"


def test_selected_scraper_source_falls_back_only_after_no_match(monkeypatch):
    scraper = _scraper_with_source("tmdb")
    calls = []

    monkeypatch.setattr(scraper, "_scrape_tmdb", lambda *args: calls.append("tmdb") or {})
    monkeypatch.setattr(
        scraper,
        "_scrape_anibk",
        lambda *args: calls.append("anibk") or {"title": "Example", "cover_url": "poster"},
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_douban",
        lambda *args: (_ for _ in ()).throw(AssertionError("unexpected Douban request")),
    )

    result = scraper.scrape("Example", category="series")

    assert calls == ["tmdb", "anibk"]
    assert result["title"] == "Example"
