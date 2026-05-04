import api from './index'
import type { Movie, MovieStats, CandidateItem } from '../types/movie'

export async function fetchMovie(moviePath: string, source?: string): Promise<{ movie: Movie }> {
  const { data } = await api.get('/api/movies/item', { params: { movie_path: moviePath, source } })
  return data
}

export async function toggleFavorite(moviePath: string): Promise<{ movie: Movie; stats: MovieStats }> {
  const { data } = await api.post('/api/movies/favorite', { movie_path: moviePath })
  return data
}

export async function addRecent(moviePath: string): Promise<{ movie: Movie; stats: MovieStats }> {
  const { data } = await api.post('/api/movies/recent', { movie_path: moviePath })
  return data
}

export async function clearRecent(): Promise<{ success: boolean; stats: MovieStats }> {
  const { data } = await api.delete('/api/movies/recent')
  return data
}

export async function playMovie(moviePath: string, episodeIndex = 0): Promise<{ success: boolean; result: unknown; stats: MovieStats }> {
  const { data } = await api.post('/api/movies/play', { movie_path: moviePath, episode_index: episodeIndex })
  return data
}

export async function updateMovie(moviePath: string, updates: Record<string, unknown>): Promise<{ movie: Movie }> {
  const { data } = await api.post('/api/movies/update', { movie_path: moviePath, updates })
  return data
}

export async function scrapeMovie(moviePath: string, customName?: string): Promise<{ movie: Movie }> {
  const { data } = await api.post('/api/movies/scrape', { movie_path: moviePath, custom_name: customName })
  return data
}

export async function searchCandidates(moviePath: string, customName?: string): Promise<{ items: CandidateItem[]; diagnostics: unknown[] }> {
  const { data } = await api.post('/api/movies/search-candidates', { movie_path: moviePath, custom_name: customName })
  return data
}

export async function applyCandidate(moviePath: string, candidate: CandidateItem): Promise<{ movie: Movie }> {
  const { data } = await api.post('/api/movies/apply-candidate', { movie_path: moviePath, candidate })
  return data
}

export async function saveProgress(moviePath: string, progress: number, duration: number): Promise<unknown> {
  const { data } = await api.post(`/api/movies/${encodeURIComponent(moviePath)}/progress`, { progress, duration })
  return data
}

export async function getProgress(moviePath: string): Promise<unknown> {
  const { data } = await api.get(`/api/movies/${encodeURIComponent(moviePath)}/progress`)
  return data
}

export async function clearProgress(moviePath: string): Promise<unknown> {
  const { data } = await api.delete(`/api/movies/${encodeURIComponent(moviePath)}/progress`)
  return data
}
