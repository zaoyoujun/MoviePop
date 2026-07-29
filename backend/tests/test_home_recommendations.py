import os
import sys
from datetime import datetime


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import db_service, library_service


def _movie(item_id: str, **overrides) -> dict:
    movie = {
        "id": item_id,
        "name": item_id,
        "title": item_id,
        "series_title": item_id,
        "source_id": "source-1",
        "source_type": "local",
        "category": "movie",
        "file_path": f"/library/movie/{item_id}/{item_id}.mkv",
        "is_series": False,
        "cover_url": f"/covers/{item_id}.jpg",
        "backdrop_url": f"/backdrops/{item_id}.jpg",
        "updated_at": "2025-01-01T00:00:00",
        "added_at": "2025-01-01T00:00:00",
        "playback": {},
        "genres": [],
        "tags": [],
        "rating": 0,
        "vote_count": 0,
    }
    movie.update(overrides)
    return movie


def test_home_hero_uses_the_active_season_or_version_without_duplicates():
    season_one = _movie(
        "show-s1",
        title="Example Show",
        series_title="Example Show",
        category="series",
        is_series=True,
        season=1,
        cover_url="/covers/show.jpg",
        backdrop_url="/backdrops/show.jpg",
        rating=7.2,
    )
    # This entry intentionally has no artwork.  The hero must still retain
    # its ID for playback and borrow only the group's visual presentation.
    season_two = _movie(
        "show-s2",
        title="Example Show Season 2",
        series_title="Example Show",
        category="series",
        is_series=True,
        season=2,
        cover_url="",
        backdrop_url="",
        playback={"percent": 45, "current_time": 900, "watch_seconds": 900},
        rating=7.2,
    )
    favorite = _movie("favorite", title="Favorite Film", is_favorite=True, rating=7.5)
    high_score = _movie(
        "high-score",
        title="High Score",
        series_title="High Score",
        rating=9.4,
        vote_count=1200,
    )
    newly_added = _movie(
        "recent",
        title="Recently Added",
        added_at="2026-07-28T00:00:00",
        rating=5.0,
    )
    duplicate_version = _movie(
        "high-score-sdr",
        title="High Score",
        series_title="High Score",
        version_title="SDR",
        rating=8.8,
    )

    now = datetime(2026, 7, 29, 12, 0, 0)
    home = library_service.build_home_data(
        [season_one, season_two, favorite, high_score, newly_added, duplicate_version],
        category=None,
        limit=12,
        now=now,
    )
    repeated = library_service.build_home_data(
        [season_one, season_two, favorite, high_score, newly_added, duplicate_version],
        category=None,
        limit=12,
        now=now,
    )

    hero_by_id = {item["id"]: item for item in home["hero"]}
    assert home["hero"] == repeated["hero"]
    assert "show-s2" in hero_by_id
    assert "show-s1" not in hero_by_id
    assert hero_by_id["show-s2"]["isResume"] is True
    assert hero_by_id["show-s2"]["recommendationReason"] == "继续观看"
    assert hero_by_id["show-s2"]["backdropUrl"] == "/backdrops/show.jpg"
    assert not {"high-score", "high-score-sdr"}.issubset(hero_by_id)


def test_home_hero_has_a_visual_and_stable_fallback_without_history_or_metadata():
    blank = _movie("blank", cover_url="", backdrop_url="", added_at="", updated_at="")
    first = _movie("first", cover_url="/covers/first.jpg", backdrop_url="", added_at="", updated_at="")
    second = _movie("second", cover_url="", backdrop_url="/backdrops/second.jpg", added_at="", updated_at="")
    now = datetime(2026, 7, 29, 12, 0, 0)

    home = library_service.build_home_data([blank, first, second], category=None, limit=12, now=now)
    repeated = library_service.build_home_data([blank, first, second], category=None, limit=12, now=now)

    assert home["hero"] == repeated["hero"]
    assert {item["id"] for item in home["hero"]} == {"first", "second"}
    assert all(item["backdropUrl"] for item in home["hero"])
    assert all(item["recommendationReason"] == "为你推荐" for item in home["hero"])


def test_added_at_is_persisted_for_recent_library_recommendations(tmp_path, monkeypatch):
    monkeypatch.setattr(db_service, "DB_PATH", str(tmp_path / "library.db"))
    db_service.init_db()
    db_service.save_library([
        {
            "id": "recent-item",
            "title": "Recent Item",
            "updated_at": "2026-07-29T00:00:00",
        }
    ])

    assert db_service.load_library()[0]["added_at"] == "2026-07-29T00:00:00"
    assert db_service.get_movie_by_id("recent-item")["added_at"] == "2026-07-29T00:00:00"
