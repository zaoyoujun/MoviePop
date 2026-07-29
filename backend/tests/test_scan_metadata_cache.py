import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import library_service, scan_service


SOURCE_ID = "source-1"


def _media_item(item_id="example-show-s1", episodes=None, **overrides):
    episodes = list(episodes or [])
    files = [f"/media/Example.Show.S01E{episode:02}.mkv" for episode in episodes]
    item = {
        "id": item_id,
        "name": "Example Show",
        "title": "Example Show",
        "series_title": "Example Show",
        "season": 1,
        "season_title": "",
        "special_type": "",
        "part": None,
        "version_title": "",
        "category": "series",
        "is_series": True,
        "episode_count": len(episodes),
        "episodes": episodes,
        "files": files,
        "file_path": files[0] if files else "/media/Example.Show.mkv",
        "source_label": "Test source",
        "cover_url": "",
        "backdrop_url": "",
        "intro": "",
        "tags": [],
    }
    item.update(overrides)
    return item


@pytest.fixture(autouse=True)
def _clear_scan_state():
    scan_service._statuses.clear()
    scan_service._cancel_events.clear()
    yield
    scan_service._statuses.clear()
    scan_service._cancel_events.clear()


def _configure_scan(monkeypatch, previous_library, scanned_items):
    source = {"id": SOURCE_ID, "name": "Test source", "type": "local"}
    saved = {}

    monkeypatch.setattr(scan_service.source_service, "load_sources", lambda: [source])
    monkeypatch.setattr(scan_service.source_service, "save_sources", lambda sources: None)
    monkeypatch.setattr(scan_service, "_collect_video_files", lambda source: ["placeholder"])
    monkeypatch.setattr(scan_service, "merge_series_videos", lambda files, label: scanned_items)
    monkeypatch.setattr(scan_service, "_auto_scrape_enabled", lambda: True)
    monkeypatch.setattr(scan_service, "_log_detected_movie", lambda movie: None)
    monkeypatch.setattr(scan_service, "_update_source_after_scan", lambda *args, **kwargs: None)
    monkeypatch.setattr(scan_service.library_service, "load_library", lambda: list(previous_library))
    monkeypatch.setattr(scan_service.library_service, "compute_stats", lambda movies: {})
    monkeypatch.setattr(
        scan_service.library_service,
        "save_library",
        lambda movies: saved.setdefault("movies", list(movies)),
    )
    return saved


def test_rescan_reuses_metadata_and_updates_new_episodes(monkeypatch):
    previous = _media_item(
        episodes=[1, 2],
        source_id=SOURCE_ID,
        metadata_title="Example Show",
        cover_url="/covers/example.webp",
        backdrop_url="/covers/example-backdrop.webp",
        intro="Existing metadata",
        tmdb_id="123",
        metadata_source="tmdb",
        playback={"current_episode": 2},
        is_favorite=True,
    )
    scanned = _media_item(episodes=[1, 2, 3])
    saved = _configure_scan(monkeypatch, [previous], [scanned])

    monkeypatch.setattr(
        scan_service,
        "_create_scraper",
        lambda: (_ for _ in ()).throw(AssertionError("cached metadata must not create a scraper")),
    )

    scan_service._scan_source(SOURCE_ID)

    saved_item = saved["movies"][0]
    assert saved_item["episodes"] == [1, 2, 3]
    assert saved_item["episode_count"] == 3
    assert saved_item["files"][-1].endswith("S01E03.mkv")
    assert saved_item["cover_url"] == "/covers/example.webp"
    assert saved_item["intro"] == "Existing metadata"
    assert saved_item["tmdb_id"] == "123"
    assert saved_item["playback"] == {"current_episode": 2}
    assert saved_item["is_favorite"] is True

    status = scan_service.get_status(SOURCE_ID)
    assert status["metadataReused"] == 1
    assert status["metadataScraped"] == 0
    assert status["episodesUpdated"] == 1


def test_rescan_scrapes_entries_without_successful_metadata(monkeypatch):
    # metadata_source alone is not enough: failed providers can set it too.
    previous = _media_item(episodes=[1], source_id=SOURCE_ID, metadata_source="tmdb")
    scanned = _media_item(episodes=[1])
    saved = _configure_scan(monkeypatch, [previous], [scanned])
    scraper = object()
    calls = []

    monkeypatch.setattr(scan_service, "_create_scraper", lambda: scraper)

    def fake_scrape(source_id, movies, scraper=None):
        calls.append((source_id, scraper, movies[0]["id"]))
        movies[0]["metadata_title"] = "Example Show"
        movies[0]["cover_url"] = "/covers/example.webp"

    monkeypatch.setattr(scan_service, "_scrape_metadata", fake_scrape)

    scan_service._scan_source(SOURCE_ID)

    assert calls == [(SOURCE_ID, scraper, "example-show-s1")]
    assert saved["movies"][0]["cover_url"] == "/covers/example.webp"
    status = scan_service.get_status(SOURCE_ID)
    assert status["metadataReused"] == 0
    assert status["metadataScraped"] == 1


def test_locked_metadata_is_preserved_without_remote_scrape(monkeypatch):
    previous = _media_item(
        episodes=[1],
        source_id=SOURCE_ID,
        metadata_locked=True,
        metadata_title="Custom title",
        intro="Custom description",
        cover_url="/covers/custom.webp",
    )
    scanned = _media_item(episodes=[1, 2])
    saved = _configure_scan(monkeypatch, [previous], [scanned])

    monkeypatch.setattr(
        scan_service,
        "_create_scraper",
        lambda: (_ for _ in ()).throw(AssertionError("locked metadata must not create a scraper")),
    )

    scan_service._scan_source(SOURCE_ID)

    saved_item = saved["movies"][0]
    assert saved_item["metadata_locked"] is True
    assert saved_item["metadata_title"] == "Custom title"
    assert saved_item["intro"] == "Custom description"
    assert saved_item["episodes"] == [1, 2]


def test_same_id_from_another_source_is_not_reused(monkeypatch):
    previous = _media_item(
        episodes=[1],
        source_id="another-source",
        metadata_title="Wrong source metadata",
        cover_url="/covers/wrong-source.webp",
    )
    scanned = _media_item(episodes=[1])
    _configure_scan(monkeypatch, [previous], [scanned])
    scraper = object()
    calls = []

    monkeypatch.setattr(scan_service, "_create_scraper", lambda: scraper)
    monkeypatch.setattr(
        scan_service,
        "_scrape_metadata",
        lambda source_id, movies, scraper=None: calls.append((source_id, scraper)),
    )

    scan_service._scan_source(SOURCE_ID)

    assert calls == [(SOURCE_ID, scraper)]


def test_home_keeps_tv_seasons_together_when_provider_categories_differ():
    season_one = _media_item(
        "example-show-s1",
        episodes=[1, 2],
        source_id=SOURCE_ID,
        category="anime",
        tmdb_media_type="tv",
    )
    season_two = _media_item(
        "example-show-s2",
        episodes=[1, 2],
        source_id=SOURCE_ID,
        category="series",
        tmdb_media_type="tv",
        season=2,
    )

    home_items = library_service._collapse_home_movies([season_one, season_two])

    assert len(home_items) == 1
    assert home_items[0]["season_count"] == 2


def test_home_keeps_scanned_series_together_without_tmdb_media_type():
    season_one = _media_item(
        "example-show-s1",
        episodes=[1, 2],
        source_id=SOURCE_ID,
        category="anime",
        tmdb_media_type="",
    )
    season_two = _media_item(
        "example-show-s2",
        episodes=[1, 2],
        source_id=SOURCE_ID,
        category="series",
        tmdb_media_type="",
        season=2,
    )

    home_items = library_service._collapse_home_movies([season_one, season_two])

    assert len(home_items) == 1
    assert home_items[0]["season_count"] == 2


def test_cached_multiseason_scan_stays_grouped_and_switchable(monkeypatch):
    previous = [
        _media_item(
            "example-show-s1",
            episodes=[1, 2],
            source_id=SOURCE_ID,
            category="anime",
            cover_url="/covers/example.webp",
        ),
        _media_item(
            "example-show-s2",
            episodes=[1, 2],
            source_id=SOURCE_ID,
            category="series",
            season=2,
            cover_url="/covers/example.webp",
        ),
    ]
    scanned = [
        _media_item("example-show-s1", episodes=[1, 2], category="anime"),
        _media_item("example-show-s2", episodes=[1, 2], category="series", season=2),
    ]
    saved = _configure_scan(monkeypatch, previous, scanned)
    monkeypatch.setattr(
        scan_service,
        "_create_scraper",
        lambda: (_ for _ in ()).throw(AssertionError("cached seasons must not rescrape")),
    )

    scan_service._scan_source(SOURCE_ID)

    saved_items = saved["movies"]
    home_items = library_service._collapse_home_movies(saved_items)
    assert len(home_items) == 1
    assert home_items[0]["season_count"] == 2

    monkeypatch.setattr(library_service, "load_library", lambda: saved_items)
    detail = library_service.movie_to_detail(saved_items[0])
    assert [season["seasonNumber"] for season in detail["seasons"]] == [1, 2]
