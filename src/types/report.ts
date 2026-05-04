export interface ReportData {
  overview: {
    total_movies: number
    favorites: number
    watched: number
    total_watch_hours: number
    avg_rating: number
  }
  type_distribution: { name: string; count: number; percent: number }[]
  genre_preferences: { tag: string; count: number }[]
  year_distribution: { name: string; count: number }[]
  source_distribution: { name: string; count: number }[]
  completion_stats: {
    completed: number
    in_progress: number
    not_started: number
  }
  recent_activity: {
    title: string
    type: string
    timestamp: number
    progress: number
  }[]
}
