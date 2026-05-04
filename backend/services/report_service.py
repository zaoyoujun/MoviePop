from __future__ import annotations

import re
from typing import Any

from utils.database import VideoCache

LOCAL_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


class ReportService:
    def __init__(self, library_service, recommendation_service) -> None:
        self.library_service = library_service
        self.recommendation_service = recommendation_service
        self.cache = VideoCache()

    def get_report(self) -> dict[str, Any]:
        movies = self.library_service.get_movies(mode="all", source="combined", search="", force_refresh=False)
        favorites = self.cache.get_favorites()
        recent_play = self.cache.get_recent_play()
        playback_data = self.cache.get_all_playback_progress()
        feedback_map = self.recommendation_service.repository.get_feedback_map()

        total = len(movies)
        fav_paths = {item.get("path") for item in favorites}
        recent_paths = {item.get("path") for item in recent_play}

        type_counter: dict[str, int] = {}
        for movie in movies:
            mtype = movie.get("type") or "视频"
            type_counter[mtype] = type_counter.get(mtype, 0) + 1

        type_distribution = []
        for name, count in sorted(type_counter.items(), key=lambda x: x[1], reverse=True):
            type_distribution.append({"name": name, "count": count, "percent": round(count / total * 100) if total else 0})

        def year_bucket(year: int) -> str:
            if year >= 2022:
                return "2022-至今"
            if year >= 2016:
                return "2016-2021"
            if year >= 2010:
                return "2010-2015"
            if year > 0:
                return "2010年以前"
            return "年份未知"

        year_counter: dict[str, int] = {}
        for movie in movies:
            bucket = year_bucket(int(movie.get("year") or 0))
            year_counter[bucket] = year_counter.get(bucket, 0) + 1

        year_distribution = [
            {"name": name, "count": count}
            for name, count in sorted(year_counter.items(), key=lambda x: x[1], reverse=True)
        ]

        source_counter: dict[str, int] = {"远程": 0, "本地": 0}
        for movie in movies:
            path = movie.get("path", "")
            if LOCAL_PATH_RE.match(path):
                source_counter["本地"] += 1
            else:
                source_counter["远程"] += 1

        source_distribution = [{"name": name, "count": count} for name, count in source_counter.items()]

        completed = 0
        in_progress = 0
        not_started = 0
        for movie in movies:
            path = movie.get("path", "")
            pb = playback_data.get(path, {})
            percent = 0
            if pb:
                progress_sec = float(pb.get("progress") or 0)
                duration_sec = float(pb.get("duration") or 0)
                if duration_sec > 0:
                    percent = min(100, round(progress_sec / duration_sec * 100))
            if percent >= 90:
                completed += 1
            elif percent > 0:
                in_progress += 1
            else:
                not_started += 1

        total_seconds = sum(float(pb.get("progress") or 0) for pb in playback_data.values())
        total_watch_hours = round(total_seconds / 3600, 1)

        ratings = [v["rating"] for v in feedback_map.values() if v.get("rating") and v["rating"] > 0]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

        profile = self.recommendation_service.repository.load_profile()
        genre_preferences = profile.get("top_tags", []) if isinstance(profile, dict) else []

        activity_items = []
        sorted_playback = sorted(
            playback_data.items(),
            key=lambda x: int(x[1].get("timestamp") or 0),
            reverse=True,
        )
        for path, pb in sorted_playback[:10]:
            movie = self.library_service.get_movie(path)
            title = movie.get("title") or movie.get("name") or path.split("/")[-1] if movie else path.split("/")[-1]
            mtype = movie.get("type") or "视频" if movie else "视频"
            progress_sec = float(pb.get("progress") or 0)
            duration_sec = float(pb.get("duration") or 0)
            percent = min(100, round(progress_sec / duration_sec * 100)) if duration_sec > 0 else 0
            activity_items.append({
                "title": title,
                "type": mtype,
                "timestamp": int(pb.get("timestamp") or 0),
                "progress": percent,
            })

        return {
            "overview": {
                "total_movies": total,
                "favorites": len(fav_paths),
                "watched": len(recent_paths),
                "total_watch_hours": total_watch_hours,
                "avg_rating": avg_rating,
            },
            "type_distribution": type_distribution,
            "genre_preferences": genre_preferences,
            "year_distribution": year_distribution,
            "source_distribution": source_distribution,
            "completion_stats": {
                "completed": completed,
                "in_progress": in_progress,
                "not_started": not_started,
            },
            "recent_activity": activity_items,
        }
