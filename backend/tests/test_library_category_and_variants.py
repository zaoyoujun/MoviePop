import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import library_service, scan_service


def _media_item(item_id="example", **overrides):
    item = {
        "id": item_id,
        "name": "Example",
        "title": "Example",
        "series_title": "Example",
        "source_id": "source-1",
        "category": "\u52a8\u6f2b",
        "file_path": "/library/\u52a8\u6f2b/Example/Example.mkv",
        "files": ["/library/\u52a8\u6f2b/Example/Example.mkv"],
        "season": 1,
        "season_title": "",
        "special_type": "",
        "chapter_name": "",
        "part": 0,
        "version_title": "",
        "is_series": True,
        "episode_count": 1,
        "episodes": [1],
        "tags": [],
        "genres": [],
    }
    item.update(overrides)
    return item


class _IncompleteTvMetadataScraper:
    def _scrape_source_order(self, category):
        return ["tmdb"]

    def scrape(self, *args, **kwargs):
        return {
            "title": "Example",
            "tmdb_media_type": "tv",
            # AniBK + TMDB artwork can legitimately have no merged genres.
            "genres": [],
        }


def test_scrape_keeps_scanned_anime_category_when_tv_metadata_has_no_genres():
    movie = _media_item()

    scan_service._scrape_metadata("source-1", [movie], scraper=_IncompleteTvMetadataScraper())

    assert movie["category"] == "\u52a8\u6f2b"
    assert movie["is_series"] is True


def test_legacy_path_repairs_anime_primary_category_without_rescan():
    legacy_movie = _media_item(
        category="\u7535\u89c6\u5267",
        file_path="/library/\u52a8\u6f2b/Example/Season 02/Example.S02E01.mkv",
        is_series=True,
        tags=["\u52a8\u6f2b"],
    )

    item = library_service.movie_to_api_format(legacy_movie)

    assert item["category"] == "anime"
    assert item["categories"] == ["anime"]
    assert item["type"] == "series"


def test_anime_movie_is_returned_for_movie_browse_category():
    anime_movie = _media_item(
        item_id="anime-film",
        title="Anime Film",
        is_series=False,
        tmdb_media_type="movie",
        episode_count=0,
        episodes=[],
    )

    home = library_service.build_home_data([anime_movie], category="movie", limit=12)

    assert [item["id"] for item in home["items"]] == ["anime-film"]
    assert home["items"][0]["categories"] == ["anime", "movie"]


def test_theatrical_anime_is_also_browsable_as_a_movie_without_tmdb_type():
    anime_movie = _media_item(
        item_id="theatrical-anime",
        special_type="\u5267\u573a\u7248",
        tmdb_media_type="",
    )

    assert library_service._api_categories(anime_movie) == ["anime", "movie"]


def test_recommendations_use_the_path_backed_category_for_each_library_item(monkeypatch):
    target = _media_item(
        item_id="target",
        title="Target",
        series_title="Target",
        category="\u7535\u5f71",
        file_path="/library/\u7535\u5f71/Target/Target.mkv",
        is_series=False,
        episode_count=0,
        episodes=[],
    )
    matching_category = _media_item(
        item_id="matching-category",
        title="Another Film",
        series_title="Another Film",
        # Simulate an old provider-overwritten value; the path says movie.
        category="\u52a8\u6f2b",
        file_path="/library/\u7535\u5f71/Another Film/Another Film.mkv",
        is_series=False,
        episode_count=0,
        episodes=[],
    )
    other_category = _media_item(
        item_id="other-category",
        title="Another Show",
        series_title="Another Show",
        file_path="/library/\u7535\u89c6\u5267/Another Show/S01E01.mkv",
    )
    monkeypatch.setattr(library_service, "get_movie_by_id", lambda _: target)
    monkeypatch.setattr(library_service, "load_library", lambda: [target, matching_category, other_category])

    recommendations = library_service.get_recommendations("target")

    assert [item["id"] for item in recommendations] == ["matching-category"]


def test_detail_keeps_each_movie_version_playback_id(monkeypatch):
    dolby = _media_item(
        item_id="movie-dolby",
        title="Example Film",
        category="\u7535\u5f71",
        file_path="/library/\u7535\u5f71/Example Film/Dolby/Example.mkv",
        is_series=False,
        episode_count=0,
        episodes=[],
        version_title="Dolby",
        tmdb_media_type="movie",
    )
    sdr = _media_item(
        item_id="movie-sdr",
        title="Example Film",
        category="\u7535\u5f71",
        file_path="/library/\u7535\u5f71/Example Film/SDR/Example.mkv",
        is_series=False,
        episode_count=0,
        episodes=[],
        version_title="SDR",
        tmdb_media_type="movie",
    )
    monkeypatch.setattr(library_service, "load_library", lambda: [dolby, sdr])

    detail = library_service.movie_to_detail(dolby)
    version_movie_ids = {
        version["versionTitle"]: version["seasons"][0]["movieId"]
        for version in detail["versions"]
    }

    assert version_movie_ids == {"Dolby": "movie-dolby", "SDR": "movie-sdr"}
