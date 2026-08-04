import os
import sys
import hashlib
from types import SimpleNamespace


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import cover_scraper
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


def test_release_date_normalization_and_metadata_merge():
    assert CoverScraper._normalize_release_date("2024-4-3") == "2024-04-03"
    assert CoverScraper._normalize_release_date("2024年4月3日") == "2024-04-03"
    assert CoverScraper._normalize_release_date("2024-02-30") == ""
    assert CoverScraper._normalize_release_date("2024") == ""

    merged = CoverScraper._merge_tmdb_artwork(
        {"title": "Example", "release_date": "", "score": 0},
        {"release_date": "2024-04-03", "score": 8.6},
    )

    assert merged["release_date"] == "2024-04-03"
    assert merged["score"] == 8.6


def test_download_cover_reuses_same_url_across_seasons(monkeypatch, tmp_path):
    image_url = "https://image.tmdb.org/t/p/original/example-image.webp"
    image_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
    existing_filename = f"Example_S1_backdrop_{image_hash}.webp"
    (tmp_path / existing_filename).write_bytes(b"existing-image")

    monkeypatch.setattr(cover_scraper, "COVERS_DIR", tmp_path)
    monkeypatch.setattr(cover_scraper, "_COVER_CACHE", {})
    monkeypatch.setattr(cover_scraper, "_URL_COVER_CACHE", {})
    monkeypatch.setattr(cover_scraper, "_COVER_CACHE_LOADED", False)

    scraper = CoverScraper.__new__(CoverScraper)
    scraper.session = SimpleNamespace(
        get=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should reuse local cover"))
    )

    result = scraper._download_cover(image_url, "Example", season=2, image_type="backdrop")

    assert result.endswith(existing_filename)
