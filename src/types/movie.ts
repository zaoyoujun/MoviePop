export interface MoviePlayback {
  progress: number
  duration: number
  percent: number
  timestamp: number
  has_progress: boolean
}

export interface Movie {
  title: string
  name: string
  type: string
  year: number | string
  intro: string
  rating: number
  duration: string
  is_series: boolean
  episodes: string[]
  episode_files: string[]
  episode_count: number
  path: string
  cover_path: string
  cover_url: string
  source: 'remote' | 'local'
  remote_provider: string | null
  source_label: string
  is_favorite: boolean
  tags: string[]
  playback: MoviePlayback
  seasons?: Record<string, string[]>
  season_count?: number
  created_at?: number
  updated_at?: number
}

export interface MovieStats {
  all: number
  remote: number
  local: number
  favorite: number
  recent: number
}

export interface CandidateItem {
  title: string
  url: string
  source: string
  year: number | null
  match_score: number | null
  matched_query: string
  strategy_source: string
}
