// API 请求封装
const configuredBackendPort = window.electronAPI?.getBackendPort?.()
const backendPort = /^\d+$/.test(configuredBackendPort || '') ? configuredBackendPort : '18987'
export const API_ORIGIN = window.location.protocol === 'file:' ? `http://127.0.0.1:${backendPort}` : ''
export const API_BASE = `${API_ORIGIN}/api`

export function apiUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE}${normalizedPath}`
}

export function assetUrl(path) {
  if (!path || typeof path !== 'string') return path
  if (/^(https?:|data:|blob:|file:)/i.test(path)) return path
  if (path.startsWith('/covers/') || path.startsWith('/static/')) {
    return `${API_ORIGIN}${path}`
  }
  return path
}

function normalizeAssetUrls(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeAssetUrls)
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, normalizeAssetUrls(item)])
    )
  }
  return assetUrl(value)
}

/**
 * 封装的请求方法
 * @param {string} url - 请求路径
 * @param {Object} options - 请求选项，支持 options.params 作为 query string
 * @returns {Promise<Object>} - 返回结果
 */
export async function request(url, options = {}) {
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json'
    }
  }

  const mergedOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...options.headers
    }
  }

  // 支持 query string 封装（POST/PUT/DELETE 也能传 params）
  let fullUrl = `${API_BASE}${url}`
  if (options.params && Object.keys(options.params).length) {
    const queryString = new URLSearchParams(
      Object.entries(options.params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString()
    if (queryString) {
      fullUrl += (url.includes('?') ? '&' : '?') + queryString
    }
  }

  try {
    const response = await fetch(fullUrl, mergedOptions)
    const text = await response.text()
    let data
    try {
      data = text ? JSON.parse(text) : {}
    } catch (parseError) {
      throw new Error(text || response.statusText || '请求失败')
    }

    if (!response.ok) {
      throw new Error(data.message || response.statusText || '请求失败')
    }

    if (data.code !== 0) {
      throw new Error(data.message || '请求失败')
    }

    return normalizeAssetUrls(data.data)
  } catch (error) {
    console.error(`API请求失败: ${url}`, error)
    throw error
  }
}

/**
 * GET 请求
 */
export function get(url, params = {}) {
  const queryString = new URLSearchParams(params).toString()
  const fullUrl = queryString ? `${url}?${queryString}` : url
  return request(fullUrl, { method: 'GET' })
}

/**
 * POST 请求
 */
export function post(url, data = {}, options = {}) {
  const init = { method: 'POST', ...options }
  // data 为 null/undefined 时不发送 body，避免 FastAPI 解析 "null" 字符串失败
  if (data !== null && data !== undefined) {
    init.body = JSON.stringify(data)
  }
  return request(url, init)
}

/**
 * POST 表单请求
 */
export function postForm(url, data = {}) {
  const formData = new URLSearchParams(data)
  return request(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: formData
  })
}

/**
 * DELETE 请求
 */
export function del(url, options = {}) {
  return request(url, { method: 'DELETE', ...options })
}

/**
 * PUT 请求
 */
export function put(url, data = {}, options = {}) {
  const init = { method: 'PUT', ...options }
  if (data !== null && data !== undefined) {
    init.body = JSON.stringify(data)
  }
  return request(url, init)
}
