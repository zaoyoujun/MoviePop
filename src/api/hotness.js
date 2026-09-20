import { get } from './request'

/**
 * 热度信号 API
 * 对应后端 hotness_series 表，存放定期拉取的外部热度时间序列。
 */

// 虚拟片库条目的热度时间序列
export function getPoolHotness(id, params = {}) {
  return get(`/pool/${id}/hotness`, params)
}

// 虚拟片库热度 Top 榜（各条目最近一次快照按 popularity 排序）
export function getTopHotness(limit = 20) {
  return get('/pool/hotness/top', { limit })
}

// 私有片库条目的热度趋势
export function getMovieHotness(movieId, params = {}) {
  return get(`/movies/${movieId}/hotness`, params)
}
