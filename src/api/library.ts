import api from './index'
import type { Movie, MovieStats } from '../types/movie'

export interface LibraryResponse {
  items: Movie[]
  stats: MovieStats
}

export async function fetchLibrary(params: {
  mode?: string
  source?: string
  search?: string
  force_refresh?: boolean
} = {}): Promise<LibraryResponse> {
  const { data } = await api.get('/api/library', { params })
  return data
}

export async function refreshLibrary(source = 'remote', autoScrape = true): Promise<{ job_id: string }> {
  const { data } = await api.post('/api/library/refresh', null, {
    params: { source, auto_scrape: autoScrape },
  })
  return data
}

export async function scrapeLibrary(source = 'remote'): Promise<{ job_id: string }> {
  const { data } = await api.post('/api/library/scrape', null, {
    params: { source },
  })
  return data
}
