<template>
  <main class="favorites-page">
    <section class="favorites-hero" :style="heroStyle">
      <div class="hero-overlay"></div>
      <div class="hero-copy">
        <span>FAVORITES</span>
        <h1>收藏片库</h1>
        <p>把想反复看的电影、剧集和动漫留在这里，下一次打开就能直接回到放映现场。</p>
      </div>
      <div class="favorite-summary">
        <article>
          <strong>{{ pagination.total }}</strong>
          <span>全部收藏</span>
        </article>
        <article>
          <strong>{{ visibleContinueCount }}</strong>
          <span>待继续</span>
        </article>
        <article>
          <strong>{{ sourceCount }}</strong>
          <span>来源数</span>
        </article>
      </div>
    </section>

    <section class="toolbar">
      <div class="search-box">
        <n-icon><Search /></n-icon>
        <input v-model.trim="keyword" type="search" placeholder="搜索收藏影片" @keyup.enter="refresh" />
      </div>
      <button class="refresh-button" :disabled="loading" type="button" @click="refresh">
        {{ loading ? '加载中' : '刷新' }}
      </button>
    </section>

    <section class="filter-row">
      <button
        v-for="item in categoryFilters"
        :key="item.value"
        :class="{ active: category === item.value }"
        type="button"
        @click="setCategory(item.value)"
      >
        {{ item.label }}
      </button>
      <span></span>
      <button
        v-for="item in sourceFilters"
        :key="item.value"
        :class="{ active: sourceType === item.value }"
        type="button"
        @click="setSource(item.value)"
      >
        {{ item.label }}
      </button>
    </section>

    <section v-if="error" class="state-card error-card">
      {{ error }}
    </section>

    <section v-else-if="loading && !favoriteMovies.length" class="state-card">
      正在加载收藏...
    </section>

    <section v-else-if="!favoriteMovies.length" class="empty-card">
      <div class="empty-mark">
        <n-icon><HeartOutline /></n-icon>
      </div>
      <h2>暂无收藏</h2>
      <p>在影片详情页或首页点亮收藏后，会出现在这里。</p>
      <button type="button" @click="goHome">去首页看看</button>
    </section>

    <section v-else class="favorite-grid">
      <article
        v-for="movie in favoriteMovies"
        :key="movie.id"
        class="media-card"
        :style="cardStyle(movie)"
        @click="goDetail(movie.id)"
      >
        <div class="card-tags">
          <span>{{ categoryLabel(movie.category) }}</span>
          <strong v-if="movie.year">{{ movie.year }}</strong>
        </div>

        <div class="card-footer">
          <div class="progress-line" :title="`播放进度 ${movie.progress?.percent || 0}%`">
            <i :style="{ width: `${clampPercent(movie.progress?.percent)}%` }"></i>
          </div>
          <strong>{{ movie.title }}</strong>
          <p>{{ movie.sourceName || sourceLabel(movie.sourceType) }}</p>
          <div class="card-actions">
            <button class="source-pill" type="button">{{ sourceLabel(movie.sourceType) }}</button>
            <button class="play-button" :disabled="playingId === movie.id" type="button" @click.stop="playMovie(movie)">
              <n-icon><Play /></n-icon>
              {{ playingId === movie.id ? '启动中' : '播放' }}
            </button>
            <button
              class="icon-button danger"
              :disabled="removingId === movie.id"
              title="取消收藏"
              type="button"
              @click.stop="unfavorite(movie)"
            >
              <n-icon><HeartDislikeOutline /></n-icon>
            </button>
          </div>
        </div>
      </article>
    </section>

    <section v-if="pagination.total > pagination.pageSize" class="pager">
      <button :disabled="pagination.page <= 1 || loading" type="button" @click="changePage(pagination.page - 1)">上一页</button>
      <span>{{ pagination.page }} / {{ totalPages }}</span>
      <button :disabled="pagination.page >= totalPages || loading" type="button" @click="changePage(pagination.page + 1)">下一页</button>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { HeartDislikeOutline, HeartOutline, Play, Search } from '@vicons/ionicons5'
import { getFavorites, playerPlay, removeFavorite } from '@/api/movie'
import { MOCK_DATA } from '@/api/mockData'
import { saveScrollPosition, scheduleScrollRestore } from '@/utils/scrollRestoration'

defineOptions({ name: 'Favorites' })

const router = useRouter()
const SCROLL_KEY = 'scroll:favorites'

const favoriteMovies = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const category = ref('all')
const sourceType = ref('all')
const playingId = ref('')
const removingId = ref('')
const pagination = ref({ page: 1, pageSize: 24, total: 0 })

const categoryFilters = [
  { label: '全部', value: 'all' },
  { label: '电影', value: 'movie' },
  { label: '剧集', value: 'series' },
  { label: '动漫', value: 'anime' }
]

const sourceFilters = [
  { label: '全部来源', value: 'all' },
  { label: 'OpenList', value: 'openlist' },
  { label: 'WebDAV', value: 'webdav' },
  { label: '本地', value: 'local' }
]

const totalPages = computed(() => Math.max(1, Math.ceil((pagination.value.total || 0) / pagination.value.pageSize)))
const sourceCount = computed(() => new Set(favoriteMovies.value.map(item => item.sourceType || 'local')).size)
const visibleContinueCount = computed(() => favoriteMovies.value.filter(item => {
  const percent = Number(item.progress?.percent || 0)
  return percent > 0 && percent < 90
}).length)
const heroStyle = computed(() => {
  const first = favoriteMovies.value[0]
  const image = first?.backdropUrl || first?.coverUrl || first?.posterUrl
  return image ? { backgroundImage: `url("${image}")` } : {}
})

let searchTimer = null
watch(keyword, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pagination.value.page = 1
    fetchFavorites()
  }, 350)
})

async function fetchFavorites() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    if (category.value !== 'all') params.category = category.value
    if (sourceType.value !== 'all') params.source_type = sourceType.value
    if (keyword.value) params.keyword = keyword.value

    const data = await getFavorites(params)
    const list = Array.isArray(data) ? data : (data?.list || data?.items || [])
    favoriteMovies.value = list
    pagination.value = {
      page: data?.pagination?.page || pagination.value.page,
      pageSize: data?.pagination?.pageSize || pagination.value.pageSize,
      total: data?.pagination?.total ?? list.length
    }
  } catch (err) {
    const fallback = MOCK_DATA.favorites || []
    favoriteMovies.value = fallback
    pagination.value.total = fallback.length
    error.value = ''
  } finally {
    loading.value = false
  }
}

function refresh() {
  pagination.value.page = 1
  fetchFavorites()
}

function setCategory(value) {
  category.value = value
  refresh()
}

function setSource(value) {
  sourceType.value = value
  refresh()
}

function changePage(page) {
  pagination.value.page = Math.max(1, Math.min(totalPages.value, page))
  fetchFavorites()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function goHome() {
  router.push({ name: 'Home' })
}

function goDetail(id) {
  saveScrollPosition(SCROLL_KEY)
  router.push({ name: 'MovieDetail', params: { id } })
}

async function playMovie(movie) {
  playingId.value = movie.id
  error.value = ''
  try {
    const firstEpisode = Array.isArray(movie.episodes) && movie.episodes.length ? movie.episodes[0] : null
    await playerPlay(movie.id, firstEpisode?.id || '', 0)
  } catch (err) {
    error.value = err?.message || '启动播放器失败'
  } finally {
    playingId.value = ''
  }
}

async function unfavorite(movie) {
  removingId.value = movie.id
  error.value = ''
  try {
    await removeFavorite(movie.id)
    favoriteMovies.value = favoriteMovies.value.filter(item => item.id !== movie.id)
    pagination.value.total = Math.max(0, pagination.value.total - 1)
    if (!favoriteMovies.value.length && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchFavorites()
    }
  } catch (err) {
    error.value = err?.message || '取消收藏失败'
  } finally {
    removingId.value = ''
  }
}

function cardStyle(movie) {
  const image = movie.coverUrl || movie.posterUrl || movie.backdropUrl || ''
  if (!image) return {}
  return { backgroundImage: `url("${image}")` }
}

function categoryLabel(value) {
  return { movie: '电影', series: '剧集', anime: '动漫', music: '音乐' }[value] || '影视'
}

function sourceLabel(value) {
  return { openlist: 'OpenList', webdav: 'WebDAV', local: '本地' }[value] || '来源'
}

function clampPercent(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.max(0, Math.min(100, number))
}

onMounted(() => {
  fetchFavorites()
  scheduleScrollRestore(SCROLL_KEY)
  window.addEventListener('scan:completed', refresh)
})

onActivated(async () => {
  await nextTick()
  scheduleScrollRestore(SCROLL_KEY)
})

onBeforeRouteLeave(() => {
  saveScrollPosition(SCROLL_KEY)
  window.removeEventListener('scan:completed', refresh)
})
</script>

<style scoped>
.favorites-page {
  min-height: 100%;
  padding: 22px 32px 52px;
  color: var(--mp-text);
  background: #030506;
}

.favorites-hero {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  min-height: 285px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(28, 23, 17, 0.94), rgba(4, 8, 10, 0.94)),
    url("https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1800&q=85");
  background-position: center;
  background-size: cover;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.38);
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(3, 5, 6, 0.96), rgba(3, 5, 6, 0.46) 58%, rgba(3, 5, 6, 0.78)),
    linear-gradient(0deg, rgba(3, 5, 6, 0.86), transparent 60%);
}

.hero-copy,
.favorite-summary {
  position: relative;
  z-index: 2;
}

.hero-copy {
  padding: 30px;
}

.hero-copy span {
  color: #5bc4f7;
  font-size: 12px;
  font-weight: 800;
}

.hero-copy h1 {
  margin: 8px 0 10px;
  color: #fff7e8;
  font-size: clamp(36px, 4vw, 56px);
  line-height: 1;
}

.hero-copy p {
  max-width: 560px;
  color: rgba(248, 243, 233, 0.66);
  font-size: 15px;
  line-height: 1.7;
}

.favorite-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(92px, 118px));
  gap: 10px;
  padding: 30px;
}

.favorite-summary article {
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(8, 11, 12, 0.62);
  backdrop-filter: blur(14px);
}

.favorite-summary strong {
  display: block;
  color: #fff7e8;
  font-size: 26px;
}

.favorite-summary span {
  color: rgba(248, 243, 233, 0.56);
  font-size: 12px;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(480px, 100%);
  height: 42px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.58);
  background: rgba(255, 255, 255, 0.05);
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

.refresh-button,
.empty-card button,
.pager button {
  height: 40px;
  padding: 0 18px;
  border: 1px solid rgba(102, 126, 234, 0.46);
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(135deg, #667eea, #764ba2);
  font-weight: 800;
  cursor: pointer;
}

.refresh-button:disabled,
.pager button:disabled,
.play-button:disabled,
.icon-button:disabled {
  cursor: default;
  opacity: 0.55;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 18px 0 24px;
}

.filter-row span {
  width: 1px;
  height: 22px;
  background: rgba(255, 255, 255, 0.1);
}

.filter-row button,
.source-pill,
.play-button,
.icon-button {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.78);
  background: rgba(255, 255, 255, 0.05);
  cursor: pointer;
}

.filter-row button {
  height: 34px;
  padding: 0 14px;
}

.filter-row button.active {
  border-color: rgba(102, 126, 234, 0.5);
  color: #5bc4f7;
  background: rgba(102, 126, 234, 0.12);
}

.favorite-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(188px, 1fr));
  gap: 12px;
}

.media-card {
  position: relative;
  min-height: 286px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(3, 5, 6, 0.08), rgba(3, 5, 6, 0.88)),
    #101315;
  background-position: center;
  background-size: cover;
  cursor: pointer;
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.media-card:hover {
  transform: translateY(-7px) scale(1.02);
  border-color: rgba(214, 169, 76, 0.44);
  box-shadow: 0 28px 58px rgba(0, 0, 0, 0.46);
}

.card-tags {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.card-tags span,
.card-tags strong {
  padding: 5px 9px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(7, 9, 10, 0.56);
  backdrop-filter: blur(10px);
  font-size: 11px;
}

.card-tags span {
  color: #46d5c5;
}

.card-footer {
  position: absolute;
  z-index: 2;
  right: 13px;
  bottom: 13px;
  left: 13px;
}

.progress-line {
  height: 4px;
  overflow: hidden;
  margin-bottom: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.17);
}

.progress-line i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #667eea, #764ba2);
}

.card-footer > strong {
  display: block;
  overflow: hidden;
  color: #fff7e8;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.86);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
}

.card-footer p {
  overflow: hidden;
  min-height: 18px;
  margin: 4px 0 11px;
  color: rgba(248, 243, 233, 0.52);
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.82);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0;
  transform: translateY(6px);
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.media-card:hover .card-actions {
  opacity: 1;
  transform: translateY(0);
}

.source-pill,
.play-button,
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 31px;
  padding: 0 10px;
  font-size: 12px;
}

.play-button {
  gap: 5px;
  border-color: rgba(102, 126, 234, 0.5);
  color: #fff;
  background: linear-gradient(135deg, #667eea, #764ba2);
  font-weight: 800;
}

.icon-button {
  width: 32px;
  padding: 0;
}

.icon-button.danger:hover {
  border-color: rgba(240, 111, 92, 0.5);
  color: #ff9b8d;
  background: rgba(240, 111, 92, 0.14);
}

.state-card,
.empty-card {
  padding: 34px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  text-align: center;
}

.empty-mark {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  margin: 0 auto 16px;
  border-radius: 50%;
  color: #f06f5c;
  background: rgba(240, 111, 92, 0.12);
  font-size: 30px;
}

.empty-card h2 {
  margin: 0 0 8px;
}

.empty-card p {
  margin: 0 0 18px;
  color: rgba(248, 243, 233, 0.58);
}

.error-card {
  color: #ff9b8d;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 28px;
}

.pager span {
  color: rgba(248, 243, 233, 0.72);
}

@media (max-width: 900px) {
  .favorites-hero,
  .toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .favorite-summary {
    width: 100%;
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 620px) {
  .favorites-page {
    padding: 16px 14px 42px;
  }

  .hero-copy,
  .favorite-summary {
    padding: 22px;
  }

  .favorite-summary,
  .favorite-grid {
    grid-template-columns: 1fr;
  }
}
</style>
