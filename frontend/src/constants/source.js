// 数据源类型配置
export const SOURCE_TYPE_LABELS = {
  webdav: 'WebDAV',
  openlist: 'OpenList',
  local: '本地'
}

// 数据源类型选项
export const SOURCE_TYPE_OPTIONS = [
  { label: 'WebDAV', value: 'WebDAV', badge: '远程' },
  { label: '内置OpenList', value: 'openlist', badge: '推荐' },
  { label: '本地存储', value: '本地存储' }
]

// 获取数据源类型标签
export function getSourceTypeLabel(type) {
  return SOURCE_TYPE_LABELS[type] || type || '未知来源'
}

// 数据源驱动配置
export const SOURCE_DRIVERS = {
  quark: '夸克网盘',
  baidu: '百度网盘'
}