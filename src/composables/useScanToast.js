/**
 * 扫描进度 Toast 全局状态
 *
 * 采用模块级 ref（ESM 单例），所有页面共享同一状态，
 * 切换路由不会丢失；将 <ScanToast /> 挂载在路由之外即可跨页常驻。
 */
import { reactive } from 'vue'

/**
 * 共享状态（模块单例）
 * - visible: 是否显示
 * - id:      当前数据源 ID
 * - message: 状态文本
 * - status:  scanning | done | error
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

/**
 * 显示 / 刷新扫描进度 Toast
 * @param {string} id       数据源 ID
 * @param {string} message  状态消息
 * @param {string} status   scanning | done | error
 * @param {Object} options  额外选项（progress, currentFile, totalFiles, processedFiles）
 */
export function showScanToast(id, message, status = 'scanning', options = {}) {
  scanToast.visible = true
  scanToast.id = id
  scanToast.message = message
  scanToast.status = status
  scanToast.progress = options.progress || 0
  scanToast.currentFile = options.currentFile || ''
  scanToast.totalFiles = options.totalFiles || 0
  scanToast.processedFiles = options.processedFiles || 0

  if (status === 'done') {
    window.dispatchEvent(new CustomEvent('scan:completed'))
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
    window.dispatchEvent(new CustomEvent('scan:completed'))
  }
}

/**
 * 手动隐藏 Toast
 */
export function hideScanToast() {
  scanToast.visible = false
}
