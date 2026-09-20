import { get } from './request'

/**
 * 发现推荐 API
 * 基于虚拟片库热度 + 用户偏好，候选不限于已拥有影片。
 */

// 个性化发现推荐（带 reason 规则短标签，冷启动时退化为热门推荐）
export function getDiscoverRecommendations(limit = 12) {
  return get('/recommend/discover', { limit })
}

// G2 AI 精排：rerank=true 走 LLM 重排+长理由（后端未启用/超时自动回退规则序）
// refresh=true 强制绕过 24h 精排缓存
export function getRerankedRecommendations(limit = 12, refresh = false) {
  return get('/recommend/discover', { limit, rerank: true, refresh })
}
