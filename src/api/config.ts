import api from './index'
import type { AppConfig, DirectoryItem } from '../types/config'

export async function fetchConfig(): Promise<AppConfig> {
  const { data } = await api.get('/api/config')
  return data
}

export async function saveConfig(payload: Partial<AppConfig>): Promise<AppConfig> {
  const { data } = await api.put('/api/config', payload)
  return data
}

export async function testConnection(payload?: Partial<AppConfig>): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post('/api/config/test', payload)
  return data
}

export async function listDirectories(path = '/'): Promise<DirectoryItem[]> {
  const { data } = await api.get('/api/directories', { params: { path } })
  return data
}

export async function listDirectoriesWithConfig(path: string, config: Partial<AppConfig>): Promise<DirectoryItem[]> {
  const { data } = await api.post('/api/directories', { ...config, path })
  return data
}

export async function listLocalDirectories(path = ''): Promise<DirectoryItem[]> {
  const { data } = await api.get('/api/local-directories', { params: { path } })
  return data
}
