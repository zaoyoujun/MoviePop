import { get, post, del } from './request'

/**
 * 虚拟片库 API
 * 对应后端 metadata_pool 表，存放 TMDB/Bangumi 精选 1 万级影视元数据。
 */

// 搜索虚拟片库（FTS5 全文检索）
export function searchPool(params = {}) {
  return get('/pool/search', params)
}

// 热门榜（按 popularity / vote_count 排序）
export function getPoolTrending(params = {}) {
  return get('/pool/trending', params)
}

// 高分榜（按 vote_average 排序）
export function getPoolTopRated(params = {}) {
  return get('/pool/top-rated', params)
}

// 虚拟片库条目详情（懒加载补全）
export function getPoolItem(id) {
  return get(`/pool/${id}`)
}

// 触发详情懒加载补全（浏览时按需拉取 TMDB 详情）
export function ensurePoolDetail(id) {
  return post(`/pool/${id}/detail`)
}

// 相似推荐：同类型+同年代
export function getPoolSimilar(id, limit = 12) {
  return get(`/pool/${id}/similar`, { limit })
}

// 想看清单
export function getWishlist() {
  return get('/wishlist')
}
export function checkWishlist(id) {
  return get(`/wishlist/${id}`)
}
export function addWishlist(id, note = '') {
  return post(`/wishlist/${id}`, { note })
}
export function removeWishlist(id) {
  return del(`/wishlist/${id}`)
}
