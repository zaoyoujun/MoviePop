import type { Movie } from './movie'

export interface RecommendationItem {
  movie: Movie
  score: number
  reasons: string[]
}

export interface ExternalRecommendation {
  title: string
  source: string
  cover_url: string
  intro: string
  year: string
  type: string
}

export interface RecommendationProfile {
  top_tags: string[]
  seed_count: number
  favorite_genres?: string[]
  favorite_years?: string[]
}

export interface RecommendationDashboard {
  items: RecommendationItem[]
  external_items: ExternalRecommendation[]
  profile: RecommendationProfile
  generated_at: number
  stats: {
    library_recommendations: number
    external_recommendations: number
    profile_tags: number
    seed_count: number
  }
}
