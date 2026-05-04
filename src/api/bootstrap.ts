import api from './index'
import type { AppConfig, MovieStats } from '../types/config'

export interface BootstrapResponse {
  config: AppConfig
  stats: MovieStats
  has_library: boolean
}

export async function fetchBootstrap(): Promise<BootstrapResponse> {
  const { data } = await api.get('/api/bootstrap')
  return data
}
