import api from './index'
import type { RecommendationDashboard } from '../types/recommendation'

export async function fetchRecommendations(limit = 18, externalLimit = 8): Promise<RecommendationDashboard> {
  const { data } = await api.get('/api/recommendations', { params: { limit, external_limit: externalLimit } })
  return data
}

export async function refreshRecommendations(): Promise<RecommendationDashboard> {
  const { data } = await api.post('/api/recommendations/refresh')
  return data
}

export async function rateMovie(moviePath: string, rating: number): Promise<unknown> {
  const { data } = await api.post('/api/recommendations/rate', { movie_path: moviePath, rating })
  return data
}
