import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import library_service


def _history_movie(item_id="show-s2", **overrides):
    item = {
        "id": item_id,
        "title": "示例剧集",
        "series_title": "示例剧集",
        "category": "series",
        "source_id": "source-1",
        "source_type": "local",
        "source_name": "本地媒体库",
        "file_path": "/library/series/Example/Season 02/Example.S02E08.mkv",
        "season": 2,
        "season_title": "最终章",
        "version_title": "Dolby Vision",
        "is_series": True,
        "episodes": [{"episode_number": 8, "title": "冰封之战"}],
        "episode_count": 12,
        "playback": {
            "current_episode": 8,
            "current_episode_id": "show-s2::ep8",
            "current_time": 120,
            "duration": 1200,
            "percent": 10,
            "last_play_time": "2026-07-29T12:00:00",
        },
    }
    item.update(overrides)
    return item


def test_continue_context_keeps_custom_season_version_and_current_episode():
    context = library_service.build_continue_watching_context(_history_movie())

    assert context["parts"] == ["最终章", "第 2 季", "Dolby Vision", "第 8 集", "冰封之战"]
    assert context["seasonLabel"] == "最终章 · 第 2 季"
    assert context["versionLabel"] == "Dolby Vision"
    assert context["episodeLabel"] == "第 8 集 · 冰封之战"


def test_continue_context_does_not_repeat_plain_custom_season_or_add_empty_movie_labels():
    plain_season = _history_movie(season=1, season_title="第一季", version_title="", playback={"current_episode": 1})
    movie = _history_movie(
        item_id="film",
        title="示例电影",
        is_series=False,
        season=1,
        season_title="",
        version_title="",
        episodes=[],
        playback={"last_play_time": "2026-07-29T11:00:00"},
    )

    assert library_service.build_continue_watching_context(plain_season)["parts"] == ["第一季", "第 1 集"]
    assert library_service.build_continue_watching_context(movie)["text"] == ""


def test_same_title_history_resources_keep_distinct_context_and_card_keys():
    first_season = _history_movie(
        item_id="show-s1-sdr",
        season=1,
        season_title="",
        version_title="SDR 标准版",
        playback={"current_episode": 3, "current_episode_id": "show-s1-sdr::ep3"},
        episodes=[{"episode_number": 3, "title": "第三集"}],
    )
    second_season = _history_movie()

    first_item = library_service.history_item_to_api_format(first_season)
    second_item = library_service.history_item_to_api_format(second_season)

    assert first_item["title"] == second_item["title"] == "示例剧集"
    assert first_item["continueContext"] == "第 1 季 · SDR 标准版 · 第 3 集"
    assert second_item["continueContext"] == "最终章 · 第 2 季 · Dolby Vision · 第 8 集 · 冰封之战"
    assert first_item["continueCardKey"] != second_item["continueCardKey"]


def test_continue_watching_records_sort_same_title_resources_by_latest_playback():
    first_season = _history_movie(
        item_id="show-s1-sdr",
        season=1,
        season_title="",
        version_title="SDR 标准版",
        playback={
            "current_episode": 3,
            "current_episode_id": "show-s1-sdr::ep3",
            "last_play_time": "2026-07-29T11:00:00",
        },
        episodes=[{"episode_number": 3, "title": "第三集"}],
    )
    second_season = _history_movie()

    records, total = library_service.continue_watching_records([first_season, second_season], page=1, page_size=6)
    history_items = [library_service.history_item_to_api_format(record) for record in records]

    assert total == 2
    assert [item["id"] for item in history_items] == ["show-s2", "show-s1-sdr"]
    assert history_items[0]["continueContext"] != history_items[1]["continueContext"]
    assert history_items[0]["continueCardKey"] != history_items[1]["continueCardKey"]


def test_history_item_api_fields_use_camel_case_names():
    item = library_service.history_item_to_api_format(_history_movie())

    assert item["continueContext"] == "最终章 · 第 2 季 · Dolby Vision · 第 8 集 · 冰封之战"
    assert item["continueContextParts"] == ["最终章", "第 2 季", "Dolby Vision", "第 8 集", "冰封之战"]
    assert item["continueSeasonLabel"] == "最终章 · 第 2 季"
    assert item["continueVersionLabel"] == "Dolby Vision"
    assert item["continueEpisodeLabel"] == "第 8 集 · 冰封之战"
    assert item["continueCardKey"] == "show-s2::show-s2::ep8"
