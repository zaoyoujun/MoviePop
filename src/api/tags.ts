import api from './index'
import type { Movie } from '../types/movie'

export async function fetchAllTags(): Promise<Record<string, number>> {
  const { data } = await api.get('/api/tags')
  return data.tags
}

export async function fetchMovieTags(moviePath: string): Promise<string[]> {
  const { data } = await api.get(`/api/movies/${encodeURIComponent(moviePath)}/tags`)
  return data.tags
}

export async function addMovieTag(moviePath: string, tag: string): Promise<{ movie: Movie }> {
  const { data } = await api.post(`/api/movies/${encodeURIComponent(moviePath)}/tags`, { tag })
  return data
}

export async function removeMovieTag(moviePath: string, tag: string): Promise<{ movie: Movie }> {
  const { data } = await api.delete(`/api/movies/${encodeURIComponent(moviePath)}/tags/${encodeURIComponent(tag)}`)
  return data
}

export async function fetchMoviesByTag(tag: string, source = 'remote'): Promise<{ items: Movie[] }> {
  const { data } = await api.get(`/api/tags/${encodeURIComponent(tag)}/movies`, { params: { source } })
  return data
}
