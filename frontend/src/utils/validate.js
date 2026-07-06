/**
 * 验证 URL 是否有效
 * @param {string} url - URL 地址
 * @returns {boolean}
 */
export function isValidUrl(url) {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

/**
 * 验证是否为空
 * @param {any} value - 值
 * @returns {boolean}
 */
export function isEmpty(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}

/**
 * 验证主机地址格式
 * @param {string} host - 主机地址
 * @returns {boolean}
 */
export function isValidHost(host) {
  // 支持域名和 IP 地址
  const domainRegex = /^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+$/
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/
  
  return domainRegex.test(host) || ipRegex.test(host)
}

/**
 * 验证端口范围
 * @param {number|string} port - 端口
 * @returns {boolean}
 */
export function isValidPort(port) {
  const portNum = parseInt(port)
  return !isNaN(portNum) && portNum >= 1 && portNum <= 65535
}