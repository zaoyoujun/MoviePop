import { get, post } from './request'

/**
 * 大模型增强 API（方向 G）
 * - 配置管理：Key 用户自配、默认关闭，后端不明文回显
 * - 连通性测试：保存前可直接带临时配置测试
 * - AI 观影报告：AI 未开启/失败时后端自动回退模板报告（data.source 区分）
 */

// 读取大模型配置（Key 仅返回 has_key 与脱敏预览）
export function getLlmSettings() {
  return get('/settings/llm')
}

// 保存大模型配置（apiKey 留空表示保持原 Key 不变，传 '__clear__' 清除）
export function saveLlmSettings(payload) {
  return post('/settings/llm', payload)
}

// 连通性测试；可传临时配置用于保存前测试
export function testLlmConnection(payload = {}) {
  return post('/llm/test', payload)
}

// AI 刮削识别演示：输入脏文件名，返回 LLM 识别出的规范片名
export function demoScrapeIdentify(filename) {
  return post('/llm/scrape-demo', { filename })
}

// 生成 AI 自然语言观影报告；forceRefresh=true 绕过缓存，includeTemplate=true 附带模板版供对比
export function generateViewingReport(days = 30, forceRefresh = false, includeTemplate = false) {
  return post('/analytics/llm-report', { days, force_refresh: forceRefresh, include_template: includeTemplate })
}

// 读取上次生成的观影报告（持久化恢复，零 LLM 成本）；report.stale=true 表示数据已更新可重新生成
export function getLastViewingReport(days = 30) {
  return get(`/analytics/llm-report/last?days=${days}`)
}
