// 影视分类配置
export const CATEGORY_LABELS = {
  all: '全部',
  movie: '电影',
  series: '剧集',
  anime: '动漫',
  variety: '综艺',
  music: '音乐',
  shorts: '短片',
  documentary: '纪录'
}

// 分类菜单选项
export const CATEGORY_OPTIONS = [
  { label: '全部', key: 'all' },
  { label: '电影', key: 'movie' },
  { label: '剧集', key: 'series' },
  { label: '动漫', key: 'anime' },
  { label: '综艺', key: 'variety' },
  { label: '音乐', key: 'music' },
  { label: '短片', key: 'shorts' },
  { label: '纪录', key: 'documentary' }
]

// 获取分类标签
export function getCategoryLabel(category) {
  return CATEGORY_LABELS[category] || category || '影视'
}