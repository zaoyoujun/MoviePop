import { ref, computed } from 'vue'
import { getHomeData, getPlayUrl } from '@/api/movie'
import { getCategoryLabel, getSourceTypeLabel } from '@/constants'

/**
 * 电影数据管理组合式函数
 */
export function useMovie() {
  const loading = ref(false)
  const error = ref('')
  const homeData = ref({
    stats: { total: 0, remote: 0, local: 0, favorite: 0 },
    hero: [],
    items: []
  })

  // 统计数据
  const stats = computed(() => homeData.value.stats)

  // Hero 数据（轮播图）
  const heroItems = computed(() => {
    return homeData.value.hero.map(normalizeHeroItem).filter(item => item.backdrop)
  })

  // 电影列表
  const movieList = computed(() => {
    return homeData.value.items.map(normalizeMovieCard).filter(item => item.cover)
  })

  // 加载首页数据
  async function loadHomeData(params = {}) {
    loading.value = true
    error.value = ''

    try {
      const data = await getHomeData(params)
      homeData.value = {
        stats: data?.stats || homeData.value.stats,
        hero: Array.isArray(data?.hero) ? data.hero : [],
        items: Array.isArray(data?.items) ? data.items : []
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '数据加载失败'
      homeData.value = {
        stats: { total: 0, remote: 0, local: 0, favorite: 0 },
        hero: [],
        items: []
      }
    } finally {
      loading.value = false
    }
  }

  // 播放电影
  // MPV 模式：不再 window.open(playUrl) 触发下载，
  // 而是通过 usePlayer 调 /api/player/play，让后端 mpv 启动
  async function playMovie(id) {
    try {
      const data = await getPlayUrl(id)
      if (!data?.id) {
        error.value = '播放信息缺失'
        return
      }
      // 从 homeData.items 中查找对应的电影项以获取封面等附加信息
      const meta = homeData.value.items.find(m => m.id === id) || {}
      await startPlay({
        movieId: data.id,
        movieTitle: meta.title || data.id,
        episodeId: data.episodeId || '',
        episodeTitle: '',
        cover: meta.coverUrl || meta.backdropUrl || '',
        episodeList: [],
        seasonIndex: 0
      })
    } catch (err) {
      error.value = err instanceof Error ? err.message : '播放失败'
    }
  }

  // 数据标准化函数
  function normalizeHeroItem(item) {
    const categoryLabel = getCategoryLabel(item.category)
    const sourceName = item.sourceName || getSourceTypeLabel(item.sourceType)
    return {
      id: item.id,
      title: item.title || '未命名影视',
      backdrop: item.backdropUrl,
      tags: Array.isArray(item.tags) && item.tags.length
        ? item.tags
        : [categoryLabel, item.year, sourceName, item.durationText].filter(Boolean)
    }
  }

  function normalizeMovieCard(item) {
    return {
      id: item.id,
      category: item.category,
      title: item.title || '未命名影视',
      type: getCategoryLabel(item.category),
      year: item.year || '',
      source: item.sourceName || getSourceTypeLabel(item.sourceType),
      cover: item.coverUrl
    }
  }

  return {
    loading,
    error,
    stats,
    heroItems,
    movieList,
    loadHomeData,
    playMovie
  }
}