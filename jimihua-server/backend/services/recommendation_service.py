from __future__ import annotations

from typing import Any

from backend.recommendations import RecommendationEngine, RecommendationRepository


class RecommendationService:
    def __init__(self, library_service) -> None:
        self.library_service = library_service
        self.repository = RecommendationRepository()
        self.engine = RecommendationEngine(self.repository)

    def get_dashboard(self, limit: int = 18, external_limit: int = 8) -> dict[str, Any]:
        profile = self.repository.load_profile()
        recommendation_payload = self.repository.load_recommendations(limit=limit)
        external_payload = self.repository.load_external_recommendations(limit=external_limit)

        if not recommendation_payload["items"]:
            refreshed = self.refresh()
            recommendation_payload = {
                "items": refreshed.get("items", [])[:limit],
                "generated_at": refreshed.get("generated_at", 0),
            }
            external_payload = {
                "items": refreshed.get("external_items", [])[:external_limit],
                "generated_at": refreshed.get("generated_at", 0),
            }
            profile = refreshed.get("profile", profile)

        return {
            "items": recommendation_payload.get("items", []),
            "external_items": external_payload.get("items", []),
            "profile": profile,
            "generated_at": max(
                int(recommendation_payload.get("generated_at") or 0),
                int(external_payload.get("generated_at") or 0),
            ),
            "stats": {
                "library_recommendations": len(recommendation_payload.get("items", [])),
                "external_recommendations": len(external_payload.get("items", [])),
                "profile_tags": len(profile.get("top_tags", [])) if isinstance(profile, dict) else 0,
                "seed_count": int(profile.get("seed_count") or 0) if isinstance(profile, dict) else 0,
            },
        }

    def refresh(self) -> dict[str, Any]:
        movies = self.library_service.get_movies(mode="all", source="combined", search="", force_refresh=False)
        payload = self.engine.generate_full_recommendations(movies)
        profile = payload.get("profile", {})
        payload["stats"] = {
            "library_recommendations": len(payload.get("items", [])),
            "external_recommendations": len(payload.get("external_items", [])),
            "profile_tags": len(profile.get("top_tags", [])) if isinstance(profile, dict) else 0,
            "seed_count": int(profile.get("seed_count") or 0) if isinstance(profile, dict) else 0,
        }
        return payload

    def rate_movie(self, movie_path: str, rating: float) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的影视条目")
        rating = max(0.0, min(5.0, float(rating)))
        self.repository.upsert_feedback(movie_path, rating=rating)
        movies = self.library_service.get_movies(mode="all", source="combined", search="", force_refresh=False)
        payload = self.engine.score_library_only(movies)
        return {
            "movie": self.library_service.get_movie(movie_path) or movie,
            "rating": rating,
            "profile": payload.get("profile", {}),
        }
