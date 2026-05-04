import api from './index'
import type { OpenListStatus, OpenListConfig, OpenListStorage, OpenListDriver, DirectoryItem } from '../types/openlist'

export async function fetchOpenListStatus(): Promise<OpenListStatus> {
  const { data } = await api.get('/api/openlist/status')
  return data
}

export async function startOpenList(): Promise<unknown> {
  const { data } = await api.post('/api/openlist/start')
  return data
}

export async function stopOpenList(): Promise<unknown> {
  const { data } = await api.post('/api/openlist/stop')
  return data
}

export async function restartOpenList(): Promise<unknown> {
  const { data } = await api.post('/api/openlist/restart')
  return data
}

export async function fetchOpenListConfig(): Promise<OpenListConfig> {
  const { data } = await api.get('/api/openlist/config')
  return data
}

export async function saveOpenListConfig(payload: Partial<OpenListConfig>): Promise<OpenListConfig> {
  const { data } = await api.put('/api/openlist/config', payload)
  return data
}

export async function downloadOpenListBinary(): Promise<{ job_id: string }> {
  const { data } = await api.post('/api/openlist/download')
  return data
}

export async function checkOpenListVersion(): Promise<{ has_update: boolean; current_version: string; latest_version: string; binary_available: boolean }> {
  const { data } = await api.get('/api/openlist/version')
  return data
}

export async function resetOpenListPassword(password: string): Promise<unknown> {
  const { data } = await api.post('/api/openlist/reset-password', { password })
  return data
}

export async function fetchOpenListDrivers(): Promise<OpenListDriver[]> {
  const { data } = await api.get('/api/openlist/drivers')
  return data.items
}

export async function fetchOpenListStorages(): Promise<OpenListStorage[]> {
  const { data } = await api.get('/api/openlist/storages')
  return data.items
}

export async function addOpenListStorage(payload: Partial<OpenListStorage>): Promise<unknown> {
  const { data } = await api.post('/api/openlist/storages', payload)
  return data
}

export async function updateOpenListStorage(payload: Partial<OpenListStorage>): Promise<unknown> {
  const { data } = await api.put('/api/openlist/storages', payload)
  return data
}

export async function deleteOpenListStorage(storageId: number): Promise<unknown> {
  const { data } = await api.delete('/api/openlist/storages', { params: { storage_id: storageId } })
  return data
}

export async function enableOpenListStorage(storageId: number): Promise<unknown> {
  const { data } = await api.post('/api/openlist/storages/enable', null, { params: { storage_id: storageId } })
  return data
}

export async function disableOpenListStorage(storageId: number): Promise<unknown> {
  const { data } = await api.post('/api/openlist/storages/disable', null, { params: { storage_id: storageId } })
  return data
}

export async function fetchOpenListDirectories(path = '/', recursive = false): Promise<DirectoryItem[]> {
  const { data } = await api.get('/api/openlist/directories', { params: { path, recursive } })
  return data
}
