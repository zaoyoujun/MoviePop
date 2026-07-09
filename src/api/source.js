import { get, post, postForm, del } from './request'

/**
 * 数据源相关 API
 */

// 获取数据源列表
export function getSources() {
  return get('/sources')
}

// 添加数据源
export function addSource(data) {
  return postForm('/sources', data)
}

// 更新数据源
export function updateSource(id, data) {
  return postForm(`/sources/${id}`, data)
}

// 删除数据源
export function deleteSource(id) {
  return del(`/sources/${id}`)
}

// 验证数据源连接
export function verifySource(data) {
  return post('/sources/verify', data)
}

// 浏览目录
export function browseDirectory(data) {
  return post('/sources/browse', data)
}

// 查询扫描状态
export function getScanStatus(sourceId) {
  return get(`/sources/${sourceId}/scan-status`)
}

// 重扫数据源
export function rescanSource(id) {
  return post(`/sources/${id}/rescan`)
}

// 取消扫描
export function cancelScan(id) {
  return post(`/sources/${id}/scan/cancel`)
}

// 挂载 OpenList 网盘并添加为数据源
export function mountOpenList(data) {
  return post('/sources/openlist/mount', data)
}