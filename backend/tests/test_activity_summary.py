import os
import sys
from datetime import datetime, timedelta


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import analytics_service


def _movie(movie_id, title, playback=None):
    return {
        "id": movie_id,
        "title": title,
        "metadata_title": title,
        "category": "movie",
        "cover_url": f"/covers/{movie_id}.webp",
        "playback": playback or {},
    }


def test_activity_summary_uses_playback_events_for_real_daily_trend(monkeypatch):
    now = datetime.now().replace(microsecond=0)
    movies = [_movie("movie-a", "Movie A"), _movie("movie-b", "Movie B")]
    events = [
        {"event_type": "play_start", "movie_id": "movie-a", "delta_seconds": 0, "created_at": now.isoformat()},
        {"event_type": "play_heartbeat", "movie_id": "movie-a", "delta_seconds": 60, "created_at": now.isoformat()},
        {"event_type": "play_start", "movie_id": "movie-b", "delta_seconds": 0, "created_at": (now - timedelta(days=1)).isoformat()},
        {"event_type": "play_heartbeat", "movie_id": "movie-b", "delta_seconds": 120, "created_at": (now - timedelta(days=1)).isoformat()},
        {"event_type": "play_heartbeat", "movie_id": "movie-a", "delta_seconds": 30, "created_at": (now - timedelta(days=3)).isoformat()},
        {"event_type": "detail_view", "movie_id": "movie-a", "delta_seconds": 0, "created_at": now.isoformat()},
    ]
    monkeypatch.setattr(analytics_service.db_service, "load_behavior_events", lambda: events)

    summary = analytics_service.build_activity_summary(7, movies)

    assert summary["dataSource"] == "events"
    assert summary["watchSeconds"] == 210
    assert summary["activeDays"] == 3
    assert summary["playCount"] == 2
    assert summary["uniqueTitles"] == 2
    assert summary["currentStreak"] == 2
    assert summary["longestStreak"] == 2
    assert len(summary["dailyTrend"]) == 7
    assert sum(item["minutes"] for item in summary["dailyTrend"]) == 3.5
    assert summary["topTitles"][0]["id"] == "movie-b"
    assert len(summary["hourDistribution"]) == 24
    assert len(summary["weekdayDistribution"]) == 7


def test_activity_summary_does_not_treat_saved_episode_progress_as_recent_activity(monkeypatch):
    now = datetime.now().replace(microsecond=0)
    series = _movie(
        "series-a",
        "Series A",
        playback={
            "episodes": {
                "ep1": {
                    "last_play_time": now.isoformat(),
                    "watch_seconds": 900,
                    "percent": 55,
                },
                "ep2": {
                    "last_play_time": now.isoformat(),
                    "current_time": 600,
                    "percent": 25,
                },
            }
        },
    )
    monkeypatch.setattr(analytics_service.db_service, "load_behavior_events", lambda: [])

    summary = analytics_service.build_activity_summary(7, [series])

    assert summary["dataSource"] == "none"
    assert summary["watchSeconds"] == 0
    assert summary["activeDays"] == 0
    assert summary["uniqueTitles"] == 0
    assert not summary["topTitles"]


def test_activity_summary_deduplicates_legacy_start_triplets_and_clamps_heartbeats(monkeypatch):
    started = datetime.now().replace(microsecond=0) - timedelta(minutes=1)
    movies = [_movie("movie-a", "Movie A")]
    events = [
        {"event_type": "play_start", "movie_id": "movie-a", "episode_id": "", "created_at": started.isoformat()},
        {"event_type": "play_start", "movie_id": "movie-a", "episode_id": "", "created_at": (started + timedelta(seconds=1)).isoformat()},
        {"event_type": "play_start", "movie_id": "movie-a", "episode_id": "", "created_at": (started + timedelta(seconds=2)).isoformat()},
        {"event_type": "play_heartbeat", "movie_id": "movie-a", "delta_seconds": 900, "created_at": (started + timedelta(seconds=3)).isoformat()},
        {"event_type": "play_start", "movie_id": "movie-a", "episode_id": "", "created_at": (started + timedelta(seconds=20)).isoformat()},
    ]
    monkeypatch.setattr(analytics_service.db_service, "load_behavior_events", lambda: events)

    summary = analytics_service.build_activity_summary(7, movies, now=started + timedelta(seconds=30))

    assert summary["dataSource"] == "events"
    assert summary["playCount"] == 2
    assert summary["watchSeconds"] == 120
    assert summary["hourDistribution"][started.hour]["value"] == 2
    assert summary["topTitles"][0]["playCount"] == 2
