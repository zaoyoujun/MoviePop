<template>
  <main class="library-page">
    <n-alert v-if="loadError" type="error" class="home-alert" :bordered="false">
      {{ loadError }}
    </n-alert>

    <section class="theater-topbar">
      <div class="search-box">
        <n-icon><Search /></n-icon>
        <input v-model.trim="keyword" type="search" placeholder="搜索电影、导演、演员..." />
      </div>
      <div ref="sortControlRef" class="sort-control">
        <button
          class="filter-button"
          :class="{ active: sortMode !== 'title-asc' }"
          type="button"
          :aria-expanded="sortMenuOpen"
          aria-haspopup="menu"
          @click="sortMenuOpen = !sortMenuOpen"
        >
          <n-icon><FunnelOutline /></n-icon>
          {{ sortMode === 'title-asc' ? '筛选' : `排序：${activeSortOption.shortLabel}` }}
        </button>

        <div v-if="sortMenuOpen" class="sort-menu" role="menu" aria-label="影视库排序">
          <div class="sort-menu-heading">排序方式</div>
          <button
            v-for="option in sortOptions"
            :key="option.value"
            class="sort-option"
            :class="{ active: sortMode === option.value }"
            type="button"
            role="menuitemradio"
            :aria-checked="sortMode === option.value"
            @click="selectSort(option.value)"
          >
            <span>{{ option.label }}</span>
            <small>{{ option.description }}</small>
          </button>
        </div>
      </div>
    </section>

    <section v-if="currentCategory === 'online'" class="online-section">
      <OnlineBrowser />
    </section>

    <HomeHero
      :items="heroItems"
      :loading="loading"
      @play="handlePlay"
      @detail="goDetail"
    />

    <HomeMediaList
      title="继续观看"
      subtitle="从上一次停下的位置继续，进度会在播放后同步"
      :cards="continueCards"
      :loading="loading"
      mode="wide"
      :showPlayback="true"
      @detail="goDetail"
      @play="handlePlay"
      @favorite="handleFavorite"
    />

    <HomeMediaList
      title="影视库"
      :subtitle="`${currentCategoryLabel}分类下共 ${visibleCards.length} 个条目`"
      :cards="visibleCards"
      :loading="loading"
      mode="poster"
      @detail="goDetail"
      @play="handlePlay"
      @favorite="handleFavorite"
    />
  </main>
</template>

<script setup>
import { computed, nextTick, onActivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import {
  FunnelOutline,
  Search
} from '@vicons/ionicons5'
import { HomeHero, HomeMediaList } from '@/components/home'
import OnlineBrowser from '@/components/online/OnlineBrowser.vue'
import { MOCK_DATA } from '@/api/mockData'
import { startPlay } from '@/composables/usePlayer'
import { addFavorite, getHistory, getHomeData, removeFavorite } from '@/api/movie'
import { getDiscoverRecommendations } from '@/api/recommend'
import { saveScrollPosition, scheduleScrollRestore, trackScrollPosition } from '@/utils/scrollRestoration'
import { consumeScanCompleted, consumeScanItemsPublished } from '@/composables/useScanToast'
import { isTestMode } from '@/utils/runtime'

defineOptions({ name: 'Home' })

const route = useRoute()
const router = useRouter()

const HOME_SORT_MODE_STORAGE_KEY = 'moviepop:home-sort-mode'
const SORT_MODE_VALUES = new Set([
  'title-asc',
  'title-desc',
  'year-desc',
  'year-asc',
  'rating-desc',
  'rating-asc'
])

function readStoredSortMode() {
  try {
    const value = window.localStorage.getItem(HOME_SORT_MODE_STORAGE_KEY)
    return SORT_MODE_VALUES.has(value) ? value : 'title-asc'
  } catch {
    return 'title-asc'
  }
}

function persistSortMode(value) {
  try {
    window.localStorage.setItem(HOME_SORT_MODE_STORAGE_KEY, value)
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
}

const loading = ref(false)
const loadError = ref('')
const keyword = ref('')
const sortMenuOpen = ref(false)
const sortMode = ref(readStoredSortMode())
const sortControlRef = ref(null)
const continueHistory = ref([])
const homeData = ref({
  stats: { total: 0, remote: 0, local: 0, favorite: 0 },
  hero: [],
  items: []
})

// The native player can return focus without changing the Vue route. Refresh
// only after a short TTL and coalesce focus/visibility events into one request.
const HOME_REVALIDATE_MS = 8 * 1000
let lastHomeLoadedAt = 0
let pendingHomeRefresh = false

const categoryLabels = {
  all: '全部',
  movie: '电影',
  series: '剧集',
  anime: '动漫',
  online: '在线',
  variety: '综艺',
  music: '音乐',
  shorts: '短片',
  documentary: '纪录',
  '4k': '4K',
  unwatched: '未观看',
  watched: '已观看'
}

const sourceTypeLabels = {
  webdav: 'WebDAV',
  openlist: 'OpenList',
  local: '本地'
}

const currentCategory = computed(() => route.query.category || 'all')
const currentCategoryLabel = computed(() => categoryLabels[currentCategory.value] || '全部')
const sortOptions = [
  { value: 'title-asc', label: '名称：A 到 Z', shortLabel: '名称', description: '按影视名称升序排列' },
  { value: 'title-desc', label: '名称：Z 到 A', shortLabel: '名称倒序', description: '按影视名称降序排列' },
  { value: 'year-desc', label: '年份：由新到旧', shortLabel: '年份', description: '优先展示上映年份较新的影视' },
  { value: 'year-asc', label: '年份：由旧到新', shortLabel: '年份倒序', description: '优先展示上映年份较早的影视' },
  { value: 'rating-desc', label: '评分：由高到低', shortLabel: '评分', description: '优先展示高评分影视' },
  { value: 'rating-asc', label: '评分：由低到高', shortLabel: '评分倒序', description: '优先展示低评分影视' }
]
const activeSortOption = computed(() =>
  sortOptions.find(option => option.value === sortMode.value) || sortOptions[0]
)

const discoverItems = ref([])

const heroItems = computed(() => {
  const localHero = homeData.value.hero
    .map(normalizeHeroItem)
    .filter(item => item.backdrop)
  // 融入 metadata_pool 发现推荐，让 1 万条精选数据在首页可见
  const poolHero = discoverItems.value
    .map(normalizePoolHeroItem)
    .filter(item => item.backdrop)
  return [...localHero, ...poolHero]
})

const rawVisibleItems = computed(() => {
  const category = currentCategory.value
  const key = keyword.value.trim().toLowerCase()
  return homeData.value.items.filter(item => {
    const itemCategories = Array.isArray(item.categories) && item.categories.length
      ? item.categories
      : [item.category]
    const matchCategory =
      category === 'all' ||
      (category === '4k' && String(item.quality || item.tags || '').toLowerCase().includes('4k')) ||
      (category === 'unwatched' && !Number(item.progress?.percent || item.progress || 0)) ||
      (category === 'watched' && Number(item.progress?.percent || item.progress || 0) >= 90) ||
      (category === 'online' && item.source_type === 'online') ||
      itemCategories.includes(category)
    const text = `${item.title || ''} ${item.sourceName || ''} ${item.year || ''}`.toLowerCase()
    return matchCategory && (!key || text.includes(key))
  })
})

const visibleCards = computed(() => sortHomeItems(rawVisibleItems.value).map((item, index) => normalizeMovieCard(item, index)))
const continueCards = computed(() =>
  continueHistory.value
    .slice(0, 6)
    .map(item => normalizeMovieCard(item))
)

function currentScrollKey() {
  return `scroll:${route.fullPath}`
}

function selectSort(value) {
  sortMode.value = SORT_MODE_VALUES.has(value) ? value : 'title-asc'
  sortMenuOpen.value = false
}

function sortHomeItems(items) {
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
  const getYear = item => Number(String(item.year || '').match(/\d{4}/)?.[0] || 0)
  const getRating = item => Number(item.rating ?? item.score ?? 0) || 0
  const compareTitle = (left, right) => collator.compare(left.title || '', right.title || '')
  const tieBreak = (left, right) => compareTitle(left, right) || String(left.id || '').localeCompare(String(right.id || ''))
  const compareMetric = (left, right, getter, direction) => {
    const leftValue = getter(left)
    const rightValue = getter(right)
    if (!leftValue && rightValue) return 1
    if (leftValue && !rightValue) return -1
    return direction * (leftValue - rightValue) || tieBreak(left, right)
  }
  const mode = sortMode.value

  return [...items].sort((left, right) => {
    if (mode === 'title-desc') return compareTitle(right, left) || tieBreak(left, right)
    if (mode === 'year-desc') return compareMetric(left, right, getYear, -1)
    if (mode === 'year-asc') return compareMetric(left, right, getYear, 1)
    if (mode === 'rating-desc') return compareMetric(left, right, getRating, -1)
    if (mode === 'rating-asc') return compareMetric(left, right, getRating, 1)
    return tieBreak(left, right)
  })
}

let abortController = null
let stopScrollTracking = () => {}

async function fetchHomeData() {
  if (abortController) abortController.abort()
  abortController = new AbortController()
  loading.value = true
  loadError.value = ''

  if (isTestMode) {
    console.info('[Home] 测试模式已启用，使用模拟首页数据')
    homeData.value = {
      stats: MOCK_DATA.stats,
      hero: MOCK_DATA.hero,
      items: MOCK_DATA.items
    }
    continueHistory.value = MOCK_DATA.items.slice(0, 6)
    loading.value = false
    lastHomeLoadedAt = Date.now()
    await nextTick()
    scheduleScrollRestore(currentScrollKey())
    if (pendingHomeRefresh) {
      pendingHomeRefresh = false
      void refreshHomeData({ force: true })
    }
    return
  }

  try {
    const params = new URLSearchParams({ limit: '200' })
    if (currentCategory.value !== 'all') params.set('category', currentCategory.value)

    const [data, historyData, discoverData] = await Promise.all([
      getHomeData(Object.fromEntries(params.entries())),
      getHistory({ page_size: '6' }),
      getDiscoverRecommendations(8).catch(() => ({ items: [] }))
    ])
    homeData.value = {
      stats: data?.stats || { total: 0, remote: 0, local: 0, favorite: 0 },
      hero: Array.isArray(data?.hero) ? data.hero : [],
      items: Array.isArray(data?.items) ? data.items : []
    }
    discoverItems.value = Array.isArray(discoverData?.items) ? discoverData.items : []
    continueHistory.value = Array.isArray(historyData?.list) ? historyData.list : []
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '首页数据加载失败'
    homeData.value = {
      stats: MOCK_DATA.stats,
      hero: MOCK_DATA.hero,
      items: MOCK_DATA.items
    }
    continueHistory.value = []
  } finally {
    loading.value = false
    lastHomeLoadedAt = Date.now()
    await nextTick()
    scheduleScrollRestore(currentScrollKey())
    if (pendingHomeRefresh) {
      pendingHomeRefresh = false
      void refreshHomeData({ force: true })
    }
  }
}

async function refreshHomeData({ force = false } = {}) {
  const stale = Date.now() - lastHomeLoadedAt >= HOME_REVALIDATE_MS
  if (loading.value) {
    // Only semantic changes (scan/category) need a second request. Focus and
    // visibility events during the initial request merely duplicate it.
    pendingHomeRefresh = pendingHomeRefresh || force
    return
  }
  if (!force && !stale) return
  await fetchHomeData()
}

function goDetail(item) {
  saveScrollPosition(currentScrollKey())
  // 兼容旧调用（传 id）和新调用（传 item 对象）
  const id = typeof item === 'object' ? item?.id : item
  const isPool = typeof item === 'object' && item.playable === false
  if (isPool) {
    // metadata_pool 条目跳转到影视数据库页并打开详情抽屉
    router.push({ name: 'Pool', query: { detail: id } })
  } else {
    router.push({ name: 'MovieDetail', params: { id } })
  }
}

async function handlePlay(id) {
  const meta = homeData.value.items.find(m => m.id === id)
    || homeData.value.hero.find(h => h.id === id)
    || {}
  await startPlay({
    movieId: id,
    movieTitle: meta.title || id,
    episodeId: '',
    episodeTitle: '',
    cover: meta.coverUrl || meta.backdropUrl || '',
    episodeList: [],
    seasonIndex: 0
  })
}

async function handleFavorite(id) {
  const meta = homeData.value.items.find(m => m.id === id)
    || homeData.value.hero.find(h => h.id === id)
  if (!meta) return

  const isFav = !!meta.isFavorite
  try {
    if (isFav) {
      await removeFavorite(id)
    } else {
      await addFavorite(id)
    }
    meta.isFavorite = !isFav
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : '收藏操作失败'
  }
}

function handleOnlineVideoAdded() {
  fetchHomeData()
}

function stripSeasonSuffix(title) {
  if (!title) return title
  return title
    .replace(/\s*第[一二三四五六七八九十\d]+季\s*$/, '')
    .replace(/\s*Season\s*\d+\s*$/i, '')
    .replace(/\s*S\d+\s*$/i, '')
    .trim()
}

function normalizeHeroItem(item) {
  const categoryLabel = categoryLabels[item.category] || item.category || '影视'
  const sourceName = item.sourceName || sourceTypeLabels[item.sourceType] || item.sourceType || '未知来源'
  return {
    id: item.id,
    title: stripSeasonSuffix(item.title) || '未命名影视',
    year: item.releaseDate || item.year || '',
    rating: Number(item.rating || item.score) > 0 ? Number(item.rating || item.score) : '',
    description: item.description || item.overview || '',
    backdrop: item.backdropUrl || item.coverUrl || item.posterUrl || '',
    recommendationReason: item.recommendationReason || '正在推荐',
    isResume: Boolean(item.isResume),
    tags: Array.isArray(item.tags) && item.tags.length
      ? item.tags
      : [categoryLabel, item.releaseDate || item.year, sourceName, item.durationText].filter(Boolean)
  }
}

function normalizePoolHeroItem(item) {
  // metadata_pool 发现推荐转成首页轮播格式；无本地播放路径，playable=false
  const TMDB_BACKDROP = 'https://image.tmdb.org/t/p/w780'
  const genres = Array.isArray(item.genres) ? item.genres.slice(0, 2) : []
  return {
    id: item.poolId || item.id,
    title: item.title || '未命名',
    year: item.year || '',
    rating: Number(item.voteAverage) > 0 ? Number(item.voteAverage).toFixed(1) : '',
    description: item.overview || '来自影视数据库的精选推荐，点击查看详情。',
    backdrop: item.backdropPath ? `${TMDB_BACKDROP}${item.backdropPath}` : '',
    recommendationReason: item.reason || '为你发现',
    isResume: false,
    playable: false,
    tags: [item.mediaType === 'tv' ? '剧集' : '电影', ...genres].filter(Boolean)
  }
}

function normalizeMovieCard(item, index = 0) {
  return {
    id: item.id,
    category: item.category,
    title: stripSeasonSuffix(item.title) || '未命名影视',
    type: categoryLabels[item.category] || item.category || '影视',
    year: item.releaseDate || item.year || '',
    source: item.sourceName || sourceTypeLabels[item.sourceType] || item.sourceType || '未知',
    continueContext: item.continueContext || '',
    cardKey: item.continueCardKey || `${item.id || item.filePath || item.title || 'media'}:${item.lastPlayTime || index}`,
    cover: item.coverUrl || item.cover || item.posterUrl || '',
    progress: Number(item.progress?.percent || item.progress || 0),
    badge: index < 4 ? 'NEW' : ''
  }
}

onMounted(() => {
  refreshHomeData({ force: true })
  scheduleScrollRestore(currentScrollKey())
  stopScrollTracking = trackScrollPosition(currentScrollKey())

  attachHomeListeners()
})

function handleScanCompleted() {
  refreshHomeData({ force: true })
}

function handleScanItemsPublished() {
  refreshHomeData({ force: true })
}

function handleWindowFocus() {
  refreshHomeData()
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible') {
    refreshHomeData()
  }
}

function handleDocumentPointerDown(event) {
  if (sortControlRef.value && !sortControlRef.value.contains(event.target)) {
    sortMenuOpen.value = false
  }
}

function attachHomeListeners() {
  window.addEventListener('scan:completed', handleScanCompleted)
  window.addEventListener('scan:items-published', handleScanItemsPublished)
  window.addEventListener('focus', handleWindowFocus)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  document.addEventListener('pointerdown', handleDocumentPointerDown)
}

function detachHomeListeners() {
  window.removeEventListener('scan:completed', handleScanCompleted)
  window.removeEventListener('scan:items-published', handleScanItemsPublished)
  window.removeEventListener('focus', handleWindowFocus)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
}

onActivated(async () => {
  attachHomeListeners()
  await nextTick()
  scheduleScrollRestore(currentScrollKey())

  // 如果扫描在其它页面已完成，激活时刷新数据
  const scanCompleted = consumeScanCompleted()
  const itemsPublished = consumeScanItemsPublished()
  if (scanCompleted || itemsPublished) {
    await refreshHomeData({ force: true })
  } else {
    await refreshHomeData()
  }
  await nextTick()
  scheduleScrollRestore(currentScrollKey())
})

watch(currentCategory, () => refreshHomeData({ force: true }))
watch(sortMode, persistSortMode)

onBeforeRouteLeave(() => {
  saveScrollPosition(currentScrollKey())
  stopScrollTracking()
  detachHomeListeners()
})

onUnmounted(() => {
  stopScrollTracking()
  detachHomeListeners()
})
</script>

<style scoped>
.library-page {
  min-height: 100%;
  padding: 22px 32px 52px;
  color: var(--mp-text);
  background:
    linear-gradient(180deg, rgba(3, 5, 6, 0.18), #030506 58%),
    #030506;
}

.home-alert {
  position: fixed;
  z-index: 40;
  top: 18px;
  right: 18px;
  max-width: 420px;
}

.theater-topbar {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 0 0 4px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(520px, 100%);
  height: 42px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.58);
  background: rgba(10, 13, 14, 0.7);
  backdrop-filter: blur(18px);
}

.search-box input {
  width: 100%;
  border: 0;
  outline: none;
  color: #fff7e8;
  background: transparent;
}

.search-box input::placeholder {
  color: rgba(248, 243, 233, 0.42);
}

.filter-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 42px;
  padding: 0 15px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.82);
  background: rgba(10, 13, 14, 0.7);
  cursor: pointer;
  backdrop-filter: blur(18px);
}

.filter-button:hover {
  border-color: rgba(102, 126, 234, 0.46);
  color: #5bc4f7;
}

.filter-button.active {
  border-color: rgba(102, 126, 234, 0.56);
  color: #b9c7ff;
  background: rgba(102, 126, 234, 0.16);
}

.sort-control {
  position: relative;
  flex: 0 0 auto;
}

.sort-menu {
  position: absolute;
  z-index: 30;
  top: calc(100% + 10px);
  right: 0;
  width: 246px;
  padding: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 12px;
  background: rgba(11, 14, 16, 0.96);
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.42);
  backdrop-filter: blur(18px);
}

.sort-menu-heading {
  padding: 8px 10px 6px;
  color: rgba(248, 243, 233, 0.52);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.sort-option {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 10px;
  border: 0;
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.84);
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.sort-option:hover,
.sort-option.active {
  color: #fff;
  background: rgba(102, 126, 234, 0.18);
}

.sort-option small {
  margin-top: 3px;
  color: rgba(248, 243, 233, 0.46);
  font-size: 11px;
}

.category-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 14px 0 18px;
  padding: 6px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
}

.category-item {
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 14px;
  color: rgba(248, 243, 233, 0.72);
  background: transparent;
  cursor: pointer;
  transition: all .2s ease;
}

.category-item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.category-item.active {
  color: #000;
  background: #63e2b7;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 18px 0 0;
}

.filter-chips span {
  width: 1px;
  height: 24px;
  margin: 0 2px;
  background: rgba(255, 255, 255, 0.1);
}

.filter-chips button {
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.7);
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
}

.filter-chips button:hover,
.filter-chips button.active,
.filter-chips .view-toggle {
  border-color: rgba(102, 126, 234, 0.46);
  color: #5bc4f7;
  background: rgba(102, 126, 234, 0.12);
}

@media (max-width: 760px) {
  .library-page {
    padding: 16px 14px 42px;
  }

  .theater-topbar {
    position: relative;
    flex-direction: column;
    align-items: stretch;
  }

  .filter-button {
    justify-content: center;
  }
}
</style>
