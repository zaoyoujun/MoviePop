import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import db_service


def _movie(movie_id, source_id, file_path):
    return {
        "id": movie_id,
        "title": movie_id,
        "source_id": source_id,
        "source_name": "Test source",
        "source_type": "openlist",
        "file_path": file_path,
        "files": [file_path],
    }


def test_changing_selected_paths_removes_only_out_of_scope_source_movies(monkeypatch, tmp_path):
    database_path = tmp_path / "library.db"
    monkeypatch.setattr(db_service, "DB_PATH", str(database_path))
    db_service.init_db()
    db_service.save_library([
        _movie("anime", "source-a", "/quark/动漫/作品/episode-01.mkv"),
        _movie("movie", "source-a", "/quark/电影/作品/movie.mkv"),
        _movie("other-source", "source-b", "/quark/电影/其它/movie.mkv"),
    ])

    removed = db_service.remove_source_movies_outside_paths("source-a", ["/quark/动漫"])
    remaining_ids = {movie["id"] for movie in db_service.load_library()}

    assert removed == 1
    assert remaining_ids == {"anime", "other-source"}

