import { get, post } from './request'

/**
 * OpenList 相关 API
 */

// 获取 OpenList 状态
export function getOpenListStatus() {
  return get('/openlist/status')
}

// 启动内置 OpenList
export function startOpenList() {
  return post('/openlist/start')
}

// 停止内置 OpenList
export function stopOpenList() {
  return post('/openlist/stop')
}

// 获取支持的网盘类型
export function getOpenListDrivers() {
  return get('/openlist/drivers')
}

// 浏览 OpenList 目录
export function browseOpenList(path, page = 1, perPage = 100) {
  return post('/openlist/browse', { path, page, per_page: perPage })
}

/**
 * 配置相关 API
 */

// 获取配置
export function getConfig() {
  return get('/config')
}

// 更新配置
export function updateConfig(data) {
  return post('/config', data)
}