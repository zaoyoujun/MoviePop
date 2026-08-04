/**
 * 扫描进度 Toast 全局状态
 *
 * 采用模块级 ref（ESM 单例），所有页面共享同一状态，
 * 切换路由不会丢失；将 <ScanToast /> 挂载在路由之外即可跨页常驻。
 */
import { reactive } from 'vue'
import { cancelScan as apiCancelScan } from '@/api/source'

/**
 * 共享状态（模块单例）
 * - visible: 是否显示
 * - id:      当前数据源 ID
 * - message: 状态文本
 * - status:  scanning | done | error | cancelled
 * - progress: 扫描进度（0-100）
 * - currentFile: 当前正在处理的文件
 * - totalFiles: 总文件数
 * - processedFiles: 已处理文件数
 */
export const scanToast = reactive({
  visible: false,
  id: '',
  message: '',
  status: 'scanning',
  progress: 0,
  currentFile: '',
  totalFiles: 0,
  processedFiles: 0
})

// 标记扫描是否已完成（用于跨页面刷新首页）
let pendingScanCompleted = false

// Set as soon as the scanner has persisted one finished resource. This lets a
// kept-alive home page revalidate while a long scrape is still running.
let pendingScanItemsPublished = false

function markScanCompleted() {
  pendingScanCompleted = true
  window.dispatchEvent(new CustomEvent('scan:completed'))
}

export function consumeScanCompleted() {
  const value = pendingScanCompleted
  pendingScanCompleted = false
  return value
}

export function markScanItemsPublished(detail = {}) {
  pendingScanItemsPublished = true
  window.dispatchEvent(new CustomEvent('scan:items-published', { detail }))
}

export function consumeScanItemsPublished() {
  const value = pendingScanItemsPublished
  pendingScanItemsPublished = false
  return value
}

// 标记用户是否已主动取消扫描（用于前端停止轮询覆盖）
let userCancelled = false

export function isUserCancelled() {
  return userCancelled
}

/**
 * 显示 / 刷新扫描进度 Toast
 * @param {string} id       数据源 ID
 * @param {string} message  状态消息
 * @param {string} status   scanning | done | error
 * @param {Object} options  额外选项（progress, currentFile, totalFiles, processedFiles）
 */
export function showScanToast(id, message, status = 'scanning', options = {}) {
  // 新扫描开始时重置用户取消标记
  if (scanToast.id !== id) {
    userCancelled = false
  }

  scanToast.visible = true
  scanToast.id = id
  scanToast.message = message
  scanToast.status = status
  scanToast.progress = options.progress || 0
  scanToast.currentFile = options.currentFile || ''
  scanToast.totalFiles = options.totalFiles || 0
  scanToast.processedFiles = options.processedFiles || 0

  if (status === 'done') {
    markScanCompleted()
  }
}

/**
 * 仅更新消息与状态（保留显示）
 * @param {string} message  状态消息
 * @param {string} status   scanning | done | error
 * @param {Object} options  额外选项
 */
export function updateScanToast(message, status, options = {}) {
  scanToast.message = message
  scanToast.status = status
  if (options.progress !== undefined) scanToast.progress = options.progress
  if (options.currentFile !== undefined) scanToast.currentFile = options.currentFile
  if (options.totalFiles !== undefined) scanToast.totalFiles = options.totalFiles
  if (options.processedFiles !== undefined) scanToast.processedFiles = options.processedFiles

  if (status === 'done') {
    markScanCompleted()
  }
}

/**
 * 取消当前扫描
 */
export async function cancelScan() {
  const id = scanToast.id
  if (!id || scanToast.status !== 'scanning') return

  userCancelled = true
  scanToast.message = '正在取消扫描...'
  try {
    await apiCancelScan(id)
    scanToast.status = 'cancelled'
    scanToast.message = '扫描已取消'
    window.dispatchEvent(new CustomEvent('scan:cancelled'))
  } catch (error) {
    userCancelled = false
    scanToast.status = 'error'
    scanToast.message = error instanceof Error ? error.message : '取消扫描失败'
  }
}

/**
 * 手动隐藏 Toast
 */
export function hideScanToast() {
  scanToast.visible = false
}
