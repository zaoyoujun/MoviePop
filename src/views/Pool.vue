<template>
  <main class="pool-page">
    <section class="pool-hero">
      <div class="hero-copy">
        <span class="eyebrow">DISCOVER</span>
        <h1>影视数据库</h1>
        <p>精选约 1 万部热门与高分影视，数据来自 TMDB，每日自动刷新热门榜。</p>
      </div>

      <div class="hero-actions">
        <div class="range-switch" role="group" aria-label="榜单类型">
          <button
            v-for="tab in tabs"
            :key="tab.value"
            type="button"
            :class="{ active: activeTab === tab.value }"
            :aria-pressed="activeTab === tab.value"
            @click="selectTab(tab.value)"
          >
            {{ tab.label }}
          </button>
        </div>
        <button
          type="button"
          class="sync-btn"
          :disabled="syncing"
          @click="startSync"
        >
          {{ syncing ? `更新中 ${Math.round(syncProgress * 100)}%` : '更新片库' }}
        </button>
      </div>
    </section>
    <!-- 元数据补全/更新进度 -->
    <div v-if="syncing" class="sync-bar">
      <div class="sync-bar-fill" :style="{ width: `${Math.round(syncProgress * 100)}%` }"></div>
      <span class="sync-bar-label">{{ syncLabel || '正在更新片库数据…' }}</span>
    </div>

    <section class="theater-topbar">
      <div class="search-box">
        <n-icon><Search /></n-icon>
        <input
          v-model.trim="keyword"
          type="search"
          placeholder="搜索片名、关键词、简介…"
          @keyup.enter="handleSearch"
        />
      </div>
      <div class="filter-chips">
        <button
          v-for="opt in mediaFilters"
          :key="opt.value"
          type="button"
          :class="{ active: mediaType === opt.value }"
          @click="selectMedia(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </section>

    <!-- 数据量提示：全部浏览 / 搜索时显示已加载与总数 -->
    <div v-if="items.length && (activeTab === 'all' || keyword)" class="pool-count-bar">
      <span>共 <strong>{{ formatNumber(filteredTotal) }}</strong> 条 · 已加载 {{ items.length }} 条</span>
      <span v-if="activeTab === 'all' && !keyword" class="count-hint">按热度排序，点击「加载更多」浏览更多</span>
    </div>

    <!-- 我的想看清单：用户主动收藏的影视（始终展示，即使搜索时） -->
    <section v-if="wishlistItems.length" class="discover-section wishlist-section">
      <div class="discover-heading">
        <div>
          <span class="eyebrow" style="color:#ff7b95">MY WISHLIST</span>
          <h2>我的想看</h2>
          <p>已收藏 {{ wishlistItems.length }} 部，点击卡片查看详情</p>
        </div>
      </div>
      <div class="discover-rail">
        <button
          v-for="item in wishlistItems"
          :key="item.pool_id"
          type="button"
          class="discover-card"
          @click="openDetail({ id: item.pool_id, poolId: item.pool_id, ...item })"
        >
          <div class="discover-poster">
            <img
              v-if="item.poster_path"
              :src="posterUrl(item.poster_path)"
              :alt="item.title"
              loading="lazy"
              @error="onPosterError"
            />
            <div v-else class="poster-placeholder">
              <span>{{ item.title?.slice(0, 1) || '?' }}</span>
            </div>
          </div>
          <div class="discover-meta">
            <strong :title="item.title">{{ item.title || '未命名' }}</strong>
            <small>
              <span v-if="item.vote_average">★ {{ Number(item.vote_average).toFixed(1) }}</span>
              <span v-if="item.year"> · {{ item.year }}</span>
            </small>
          </div>
        </button>
      </div>
    </section>

    <!-- 为你发现：基于热度 + 偏好的推荐（搜索/筛选时隐藏） -->
    <section v-if="!keyword && (discoverItems.length || reranking)" class="discover-section">
      <div class="discover-heading">
        <div>
          <span class="eyebrow">FOR YOU</span>
          <h2>{{ discoverColdStart ? '热门发现' : '为你发现' }}</h2>
          <p>{{ discoverHeadingDesc }}</p>
        </div>
        <div v-if="rerankSupported || discoverMeta.snapshotDate" class="discover-actions">
          <span v-if="discoverMeta.snapshotDate" class="discover-fresh">
            热度数据截至 {{ discoverMeta.snapshotDate }}
            <template v-if="discoverMeta.reranked">
              · AI 精排<span v-if="discoverMeta.cached">（缓存）</span>
            </template>
          </span>
          <button
            v-if="rerankSupported && !discoverColdStart"
            type="button"
            class="rerank-btn"
            :disabled="reranking"
            @click="runRerank(false)"
          >
            <span v-if="reranking" class="rerank-spinner" aria-hidden="true"></span>
            {{ reranking ? 'AI 精排中…' : (discoverMeta.reranked ? '刷新 AI 精排' : 'AI 精排') }}
          </button>
        </div>
      </div>

      <!-- AI 精排骨架：LLM 调用约数秒，期间用 shimmer 占位 -->
      <div v-if="reranking" class="discover-rail discover-skeleton" aria-live="polite">
        <div v-for="n in 12" :key="n" class="skeleton-card">
          <div class="skeleton-poster"></div>
          <div class="skeleton-line"></div>
        </div>
      </div>

      <div v-else class="discover-rail">
        <button
          v-for="item in discoverItems"
          :key="item.poolId"
          type="button"
          class="discover-card"
          @click="openDetail(item)"
        >
          <div class="discover-poster">
            <img
              v-if="item.posterPath"
              :src="posterUrl(item.posterPath)"
              :alt="item.title"
              loading="lazy"
              @error="onPosterError"
            />
            <div v-else class="poster-placeholder">
              <span>{{ item.title?.slice(0, 1) || '?' }}</span>
            </div>
            <span
              class="discover-reason"
              :class="{ 'discover-reason-ai': item.reasonSource === 'llm' }"
            >
              <span v-if="item.reasonSource === 'llm'" class="ai-badge">AI</span>{{ item.reason }}
            </span>
            <span v-if="item.owned" class="discover-owned">已入库</span>
          </div>
          <div class="discover-meta">
            <strong :title="item.title">{{ item.title || '未命名' }}</strong>
            <small>
              <span v-if="item.voteAverage">★ {{ Number(item.voteAverage).toFixed(1) }}</span>
              <span v-if="item.year"> · {{ item.year }}</span>
            </small>
            <small v-if="item.reasonDetail" class="discover-ai-reason">{{ item.reasonDetail }}</small>
          </div>
        </button>
      </div>
    </section>

    <section v-if="loading && !items.length" class="state-card" aria-live="polite">
      正在拉取影视数据…
    </section>

    <section v-else-if="!items.length" class="state-card" aria-live="polite">
      <strong>暂无数据</strong>
      <p>{{ emptyHint }}</p>
      <button v-if="!poolCount" type="button" class="retry-button" @click="goFirstBoot">
        前往初始化下载
      </button>
    </section>

    <template v-else>
      <section v-if="error" class="notice-card" role="status">
        <span>最新数据同步失败，当前显示上次结果。</span>
        <button type="button" @click="loadData">重试</button>
      </section>

      <section class="pool-grid" aria-label="影视列表">
        <article
          v-for="item in items"
          :key="item.id"
          class="pool-card"
          @click="openDetail(item)"
        >
          <div class="card-poster">
            <img
              v-if="item.posterPath"
              :src="posterUrl(item.posterPath)"
              :alt="item.title"
              loading="lazy"
              @error="onPosterError"
            />
            <div v-else class="poster-placeholder">
              <span>{{ item.title?.slice(0, 1) || '?' }}</span>
            </div>
            <span v-if="item.voteAverage" class="card-rating">
              ★ {{ Number(item.voteAverage).toFixed(1) }}
            </span>
          </div>
          <div class="card-meta">
            <h3 :title="item.title">{{ item.title || '未命名' }}</h3>
            <p>
              <span v-if="item.year">{{ item.year }}</span>
              <span v-if="item.mediaType" class="type-badge">{{ typeLabel(item.mediaType) }}</span>
            </p>
          </div>
        </article>
      </section>

      <section v-if="hasMore" class="load-more-row">
        <button type="button" class="load-more-btn" :disabled="loading" @click="loadMore">
          {{ loading ? '加载中…' : '加载更多' }}
        </button>
        <span class="load-more-info">已加载 {{ items.length }} / {{ formatNumber(filteredTotal) }} 条</span>
      </section>
    </template>

    <!-- 详情抽屉 -->
    <transition name="drawer">
      <section v-if="detailVisible" class="detail-drawer" role="dialog" aria-label="影视详情">
        <button class="drawer-close" type="button" @click="closeDetail">×</button>
        <div v-if="detailLoading" class="detail-loading">正在补全详情…</div>
        <template v-else-if="detailItem">
          <img
            v-if="detailItem.backdropPath"
            class="detail-backdrop"
            :src="backdropUrl(detailItem.backdropPath)"
            :alt="detailItem.title"
          />
          <div class="detail-body">
            <h2>{{ detailItem.title }}</h2>
            <p v-if="detailItem.originalTitle" class="detail-original">
              {{ detailItem.originalTitle }}
            </p>
            <div class="detail-facts">
              <span v-if="detailItem.year">{{ detailItem.year }}</span>
              <span v-if="detailItem.runtime">{{ detailItem.runtime }} 分钟</span>
              <span v-if="detailItem.voteAverage">★ {{ Number(detailItem.voteAverage).toFixed(1) }}</span>
              <span v-if="detailItem.voteCount">{{ formatNumber(detailItem.voteCount) }} 人评分</span>
              <span v-if="detailItem.status" class="type-badge">{{ detailItem.status }}</span>
            </div>
            <div v-if="detailGenres.length" class="detail-genres">
              <span v-for="g in detailGenres" :key="g" class="genre-tag">{{ g }}</span>
            </div>
            <p v-if="detailItem.overview" class="detail-overview">{{ detailItem.overview }}</p>
            <p v-else class="detail-overview empty">暂无简介</p>

            <div class="detail-actions-row">
              <button
                type="button"
                class="wishlist-btn"
                :class="{ active: inWishlist }"
                :disabled="wishlistLoading"
                @click="toggleWishlist"
              >
                <span class="wishlist-icon">{{ inWishlist ? '♥' : '♡' }}</span>
                {{ inWishlist ? '已加入想看' : '加入想看' }}
              </button>
            </div>

            <!-- 相似推荐：让 1 万条影视库在详情页产生关联价值 -->
            <section v-if="similarItems.length" class="detail-similar">
              <h3 class="similar-title">相似推荐</h3>
              <div class="similar-grid">
                <button
                  v-for="sim in similarItems"
                  :key="sim.id"
                  type="button"
                  class="similar-card"
                  @click="openSimilar(sim)"
                >
                  <img
                    v-if="sim.posterPath"
                    :src="posterUrl(sim.posterPath)"
                    :alt="sim.title"
                    loading="lazy"
                    @error="onPosterError"
                  />
                  <div class="similar-info">
                    <span class="similar-name">{{ sim.title }}</span>
                    <span class="similar-meta">
                      {{ sim.year || '' }}
                      <template v-if="sim.voteAverage"> · ★{{ Number(sim.voteAverage).toFixed(1) }}</template>
                    </span>
                  </div>
                </button>
              </div>
            </section>
          </div>
        </template>
      </section>
    </transition>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@vicons/ionicons5'
import { getPoolTrending, getPoolTopRated, searchPool, ensurePoolDetail, getPoolSimilar, checkWishlist, addWishlist, removeWishlist, getWishlist } from '@/api/pool'
import { getDiscoverRecommendations, getRerankedRecommendations } from '@/api/recommend'
import { getLlmSettings } from '@/api/llm'
import { refreshAll, getJobsStatus } from '@/api/jobs'
import { get } from '@/api/request'

defineOptions({ name: 'Pool' })

const router = useRouter()
const route = useRoute()

const TMDB_IMG = 'https://image.tmdb.org/t/p/w342'
const TMDB_BACKDROP = 'https://image.tmdb.org/t/p/w780'

const tabs = [
  { value: 'all', label: '全部' },
  { value: 'trending', label: '热门榜' },
  { value: 'top-rated', label: '高分榜' }
]
const mediaFilters = [
  { value: '', label: '全部' },
  { value: 'movie', label: '电影' },
  { value: 'tv', label: '剧集' }
]

const activeTab = ref('all')
const mediaType = ref('')
const keyword = ref('')
const items = ref([])
const loading = ref(false)
const error = ref('')
const page = ref(1)
const perPage = ref(24)
const hasMore = ref(false)
const poolCount = ref(0)
const filteredTotal = ref(0)

const discoverItems = ref([])
const discoverColdStart = ref(false)
const discoverMeta = ref({
  reranked: false,
  cached: false,
  snapshotDate: '',
  fallbackReason: ''
})
const reranking = ref(false)
const rerankSupported = ref(false)
const wishlistItems = ref([])

// 元数据补全/更新任务（拉取 TMDB 榜单 + 按年份发现，去重后约 1 万部）
const syncing = ref(false)
const syncProgress = ref(0)
const syncLabel = ref('')
let syncTimer = null

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailItem = ref(null)
const similarItems = ref([])
const inWishlist = ref(false)
const wishlistLoading = ref(false)

const detailGenres = computed(() => {
  const g = detailItem.value?.genres
  return Array.isArray(g) ? g : []
})

const discoverHeadingDesc = computed(() => {
  if (discoverMeta.value.reranked) {
    return discoverMeta.value.cached
      ? 'AI 已按你的偏好重新排序（24 小时缓存结果）'
      : 'AI 已结合你的观看偏好重新排序并给出理由'
  }
  if (discoverColdStart.value) return '基于 TMDB 实时热度推荐'
  return '结合你的观看偏好与外部热度'
})

const emptyHint = computed(() => {
  if (keyword.value) return '没有匹配的影视，换个关键词试试。'
  if (!poolCount.value) return '虚拟片库尚未下载，请先完成首次初始化。'
  return '当前筛选条件下没有数据。'
})

function posterUrl(path) {
  return `${TMDB_IMG}${path}`
}

function backdropUrl(path) {
  return `${TMDB_BACKDROP}${path}`
}

function typeLabel(t) {
  if (t === 'movie') return '电影'
  if (t === 'tv') return '剧集'
  return t || ''
}

function formatNumber(n) {
  const num = Number(n || 0)
  if (num >= 10000) return `${(num / 10000).toFixed(1)}万`
  return String(num)
}

function onPosterError(e) {
  e.target.style.display = 'none'
}

function selectTab(tab) {
  if (activeTab.value === tab) return
  activeTab.value = tab
  keyword.value = ''
  resetAndLoad()
}

function selectMedia(m) {
  if (mediaType.value === m) return
  mediaType.value = m
  resetAndLoad()
}

function handleSearch() {
  resetAndLoad()
}

function resetAndLoad() {
  page.value = 1
  items.value = []
  hasMore.value = false
  loadData()
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const params = { media_type: mediaType.value, per_page: perPage.value }
    if (keyword.value) {
      // 关键词搜索走 FTS5 全文检索，支持分页
      params.q = keyword.value
      params.page = page.value
      const data = await searchPool(params)
      const list = data?.items || []
      items.value = page.value === 1 ? list : [...items.value, ...list]
      filteredTotal.value = data?.total ?? items.value.length
      hasMore.value = list.length >= perPage.value
    } else if (activeTab.value === 'trending') {
      const data = await getPoolTrending({ media_type: mediaType.value, per_page: 50 })
      items.value = data?.items || []
      filteredTotal.value = items.value.length
      hasMore.value = false
    } else if (activeTab.value === 'top-rated') {
      const data = await getPoolTopRated({ media_type: mediaType.value, per_page: 50 })
      items.value = data?.items || []
      filteredTotal.value = items.value.length
      hasMore.value = false
    } else {
      // 全部浏览：按热度排序，分页加载全量片库
      params.sort = 'popularity'
      params.page = page.value
      const data = await searchPool(params)
      const list = data?.items || []
      items.value = page.value === 1 ? list : [...items.value, ...list]
      filteredTotal.value = data?.total ?? items.value.length
      hasMore.value = items.value.length < filteredTotal.value
    }
    poolCount.value = (await get('/pool/count'))?.count || 0
  } catch (err) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || loading.value) return
  // 仅「全部」浏览和关键词搜索支持加载更多；榜单固定 top 50
  if (activeTab.value !== 'all' && !keyword.value) return
  page.value += 1
  await loadData()
}

async function openDetail(item) {
  detailVisible.value = true
  detailLoading.value = true
  detailItem.value = item
  similarItems.value = []
  inWishlist.value = false
  try {
    const poolId = item.id || item.poolId
    const data = await ensurePoolDetail(poolId)
    detailItem.value = data || item
    // 加载相似推荐（静默失败不影响详情展示）
    try {
      const similar = await getPoolSimilar(poolId, 10)
      similarItems.value = (similar?.items || []).filter(s => s.id !== poolId)
    } catch { /* 相似推荐失败静默 */ }
    // 检查是否已在想看清单
    try {
      const check = await checkWishlist(poolId)
      inWishlist.value = !!check?.inWishlist
    } catch { /* 静默 */ }
  } catch (err) {
    // 保持已有信息
  } finally {
    detailLoading.value = false
  }
}

/** 在抽屉内直接切换到另一条相似条目 */
async function openSimilar(item) {
  await openDetail(item)
}

async function toggleWishlist() {
  const poolId = detailItem.value?.id || detailItem.value?.poolId
  if (!poolId || wishlistLoading.value) return
  wishlistLoading.value = true
  try {
    if (inWishlist.value) {
      await removeWishlist(poolId)
      inWishlist.value = false
    } else {
      await addWishlist(poolId)
      inWishlist.value = true
    }
    // 刷新顶部想看清单
    await loadWishlist()
  } finally {
    wishlistLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detailItem.value = null
  similarItems.value = []
  inWishlist.value = false
}

function goFirstBoot() {
  router.push({ name: 'FirstBoot' })
}

function applyDiscoverData(data) {
  discoverItems.value = data?.items || []
  discoverColdStart.value = !!data?.coldStart
  discoverMeta.value = {
    reranked: !!data?.reranked,
    cached: !!data?.cached,
    snapshotDate: data?.snapshotDate || '',
    fallbackReason: data?.fallbackReason || ''
  }
}

async function loadDiscover() {
  try {
    const data = await getDiscoverRecommendations(12)
    applyDiscoverData(data)
  } catch {
    discoverItems.value = []
  }
}

// G2：AI 精排（后端开关关闭/冷启动/超时都会自动回退规则序，这里只负责呈现）
async function runRerank(refresh = false) {
  if (reranking.value) return
  reranking.value = true
  try {
    const data = await getRerankedRecommendations(12, refresh)
    applyDiscoverData(data)
  } catch {
    // 单次精排失败保留当前规则结果，不清空页面
  } finally {
    reranking.value = false
  }
}

async function checkRerankSupported() {
  try {
    const d = await getLlmSettings()
    const enabled = !!(d?.llm_enabled ?? d?.llmEnabled)
    const rerankOn = !!(d?.llm_rerank_enabled ?? d?.llmRerankEnabled)
    rerankSupported.value = enabled && rerankOn
  } catch {
    rerankSupported.value = false
  }
}

async function loadWishlist() {
  try {
    const data = await getWishlist()
    wishlistItems.value = data?.items || []
  } catch {
    wishlistItems.value = []
  }
}

function stopSyncTimer() {
  if (syncTimer) {
    clearInterval(syncTimer)
    syncTimer = null
  }
}

async function pollSyncStatus() {
  try {
    const all = await getJobsStatus()
    const job = all?.pool_initial
    if (!job) return
    syncing.value = !!job.running
    syncProgress.value = job.progress || 0
    syncLabel.value = job.label || ''
    if (!job.running) {
      stopSyncTimer()
      // 完成后重新加载列表与推荐
      await Promise.all([loadData(), loadDiscover()])
    }
  } catch {
    // 单次轮询失败忽略，下一轮重试
  }
}

async function startSync() {
  if (syncing.value) return
  try {
    await refreshAll()
  } catch {
    // 后端可能返回"任务正在进行中"，继续轮询进度即可
  }
  syncing.value = true
  syncProgress.value = 0
  await pollSyncStatus()
  if (syncing.value && !syncTimer) {
    syncTimer = setInterval(pollSyncStatus, 1500)
  }
}

onMounted(async () => {
  await loadData()
  loadDiscover()
  loadWishlist()
  checkRerankSupported()
  // 从首页 discover 推荐跳转过来时，自动打开对应条目的详情抽屉
  const detailId = route.query.detail
  if (detailId) {
    const target = items.value.find(i => i.id === detailId)
      || discoverItems.value.find(i => (i.poolId || i.id) === detailId)
    if (target) {
      openDetail(target)
    }
  }
  // 若进入页面时已有补全任务在跑（如刚完成首次引导），自动接续进度
  getJobsStatus()
    .then((all) => {
      if (all?.pool_initial?.running) {
        syncing.value = true
        syncTimer = setInterval(pollSyncStatus, 1500)
      }
    })
    .catch(() => {})
})

onUnmounted(stopSyncTimer)
watch(activeTab, () => {})
</script>

<style scoped>
.pool-page {
  min-height: 100%;
  padding: 24px 32px 56px;
  color: var(--mp-text);
  background:
    radial-gradient(circle at 92% 2%, rgba(102, 126, 234, 0.2), transparent 29rem),
    radial-gradient(circle at 3% 18%, rgba(118, 75, 162, 0.14), transparent 23rem),
    var(--mp-bg);
}

.pool-hero {
  display: flex;
  gap: 28px;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 22px;
  padding: 30px;
  border-radius: 18px;
  background:
    linear-gradient(118deg, rgba(118, 75, 162, 0.18), rgba(102, 126, 234, 0.08) 52%, transparent),
    var(--mp-panel-strong);
}

.hero-copy .eyebrow {
  display: block;
  color: var(--mp-text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  line-height: 1.2;
}

.pool-hero h1 {
  margin: 8px 0 6px;
  color: var(--mp-text);
  font-size: 28px;
  letter-spacing: -0.02em;
}

.pool-hero p {
  margin: 0;
  color: var(--mp-text-soft);
  font-size: 13px;
}

.hero-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 12px;
}

.range-switch {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--mp-line);
  border-radius: 10px;
  background: rgba(10, 13, 14, 0.5);
}

.range-switch button {
  padding: 7px 16px;
  border: 0;
  border-radius: 7px;
  color: var(--mp-text-soft);
  background: transparent;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.range-switch button:hover {
  color: var(--mp-text);
  background: rgba(255, 255, 255, 0.06);
}

.range-switch button.active {
  color: #fff;
  background: linear-gradient(135deg, var(--mp-gold), var(--mp-teal));
}

.sync-btn {
  padding: 9px 18px;
  border: 1px solid rgba(102, 126, 234, 0.5);
  border-radius: 10px;
  color: #cdd6ff;
  background: rgba(102, 126, 234, 0.14);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s ease;
}

.sync-btn:hover:not(:disabled) {
  color: #fff;
  border-color: rgba(102, 126, 234, 0.9);
  background: rgba(102, 126, 234, 0.28);
}

.sync-btn:disabled {
  opacity: 0.7;
  cursor: default;
}

.sync-bar {
  position: relative;
  height: 34px;
  margin: -6px 0 18px;
  border: 1px solid rgba(102, 126, 234, 0.28);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(10, 13, 14, 0.7);
}

.sync-bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, rgba(102, 126, 234, 0.35), rgba(118, 75, 162, 0.55));
  transition: width 0.4s ease;
}

.sync-bar-label {
  position: relative;
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 14px;
  color: #dfe4ff;
  font-size: 12px;
}

.theater-topbar {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(520px, 100%);
  height: 42px;
  padding: 0 14px;
  border: 1px solid var(--mp-line);
  border-radius: 10px;
  color: var(--mp-text-muted);
  background: var(--mp-panel);
}

.search-box input {
  width: 100%;
  border: 0;
  outline: none;
  color: var(--mp-text);
  background: transparent;
}

.search-box input::placeholder {
  color: var(--mp-text-muted);
}

.filter-chips {
  display: flex;
  gap: 8px;
}

.filter-chips button {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--mp-line);
  border-radius: 8px;
  color: var(--mp-text-soft);
  background: rgba(255, 255, 255, 0.04);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-chips button:hover,
.filter-chips button.active {
  border-color: rgba(102, 126, 234, 0.46);
  color: #b9c7ff;
  background: rgba(102, 126, 234, 0.16);
}

.pool-count-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 0 4px;
  color: var(--mp-text-muted);
  font-size: 12px;
}

.pool-count-bar strong {
  color: var(--mp-text);
  font-weight: 700;
}

.count-hint {
  color: var(--mp-text-muted);
}

.state-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 24px;
  border: 1px solid var(--mp-line);
  border-radius: 14px;
  color: var(--mp-text-soft);
  background: var(--mp-panel);
  text-align: center;
}

.retry-button {
  margin-top: 8px;
  padding: 8px 20px;
  border: 1px solid rgba(102, 126, 234, 0.46);
  border-radius: 8px;
  color: #b9c7ff;
  background: rgba(102, 126, 234, 0.16);
  cursor: pointer;
}

.notice-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding: 10px 16px;
  border: 1px solid rgba(232, 90, 90, 0.32);
  border-radius: 10px;
  color: #e8a85a;
  background: rgba(232, 90, 90, 0.08);
}

.notice-card button {
  padding: 4px 12px;
  border: 1px solid rgba(232, 90, 90, 0.4);
  border-radius: 6px;
  color: #e8a85a;
  background: transparent;
  cursor: pointer;
}

.discover-section {
  margin-bottom: 28px;
}

.discover-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}

.discover-heading .eyebrow {
  display: block;
  color: var(--mp-text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.discover-heading h2 {
  margin: 4px 0 2px;
  color: var(--mp-text);
  font-size: 20px;
}

.discover-heading p {
  margin: 0;
  color: var(--mp-text-soft);
  font-size: 12px;
}

.discover-rail {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 10px;
  scroll-snap-type: x mandatory;
}

.discover-rail::-webkit-scrollbar {
  height: 6px;
}

.discover-rail::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 999px;
}

.discover-card {
  flex: 0 0 148px;
  scroll-snap-align: start;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.discover-card:hover {
  transform: translateY(-3px);
}

.discover-poster {
  position: relative;
  aspect-ratio: 2 / 3;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.04);
}

.discover-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.discover-reason {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea, #764ba2);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
}

.discover-owned {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 2px 7px;
  border-radius: 6px;
  color: #46d5c5;
  font-size: 10px;
  font-weight: 700;
  background: rgba(0, 0, 0, 0.72);
}

.discover-meta {
  padding: 8px 2px 0;
}

.discover-meta strong {
  display: block;
  color: #fff7e8;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.discover-meta small {
  color: rgba(248, 243, 233, 0.5);
  font-size: 11px;
}

.discover-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.discover-fresh {
  color: var(--mp-text-muted);
  font-size: 11px;
}

.rerank-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid rgba(102, 126, 234, 0.5);
  border-radius: 999px;
  color: #cdd6ff;
  font-size: 12px;
  font-weight: 600;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.22), rgba(118, 75, 162, 0.22));
  cursor: pointer;
  transition: all 0.2s ease;
}

.rerank-btn:hover:not(:disabled) {
  border-color: rgba(102, 126, 234, 0.9);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.38), rgba(118, 75, 162, 0.38));
}

.rerank-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.rerank-spinner {
  width: 11px;
  height: 11px;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: #cdd6ff;
  border-radius: 50%;
  animation: rerank-spin 0.7s linear infinite;
}

@keyframes rerank-spin {
  to { transform: rotate(360deg); }
}

.discover-reason-ai {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);
}

.ai-badge {
  display: inline-block;
  margin-right: 4px;
  padding: 0 4px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.04em;
  background: rgba(255, 255, 255, 0.25);
}

.discover-ai-reason {
  display: -webkit-box;
  margin-top: 3px;
  color: rgba(245, 184, 110, 0.85);
  font-size: 11px;
  line-height: 1.45;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.discover-skeleton {
  overflow: hidden;
}

.skeleton-card {
  flex: 0 0 148px;
}

.skeleton-poster {
  aspect-ratio: 2 / 3;
  border-radius: 10px;
}

.skeleton-line {
  height: 12px;
  margin: 10px 2px 0;
  border-radius: 6px;
}

.skeleton-poster,
.skeleton-line {
  background: linear-gradient(90deg,
    rgba(255, 255, 255, 0.05) 25%,
    rgba(255, 255, 255, 0.11) 37%,
    rgba(255, 255, 255, 0.05) 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
}

@keyframes skeleton-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}

.pool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: 18px;
}

.pool-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.pool-card:hover {
  transform: translateY(-3px);
}

.card-poster {
  position: relative;
  aspect-ratio: 2 / 3;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--mp-line);
}

.card-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poster-placeholder {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  color: var(--mp-text-muted);
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12), rgba(118, 75, 162, 0.12));
}

.card-rating {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--mp-text);
  font-size: 11px;
  font-weight: 700;
  background: rgba(0, 0, 0, 0.7);
}

.card-meta h3 {
  margin: 0;
  color: var(--mp-text);
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta p {
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 2px 0 0;
  color: var(--mp-text-muted);
  font-size: 11px;
}

.type-badge {
  padding: 1px 6px;
  border-radius: 4px;
  color: #b9c7ff;
  background: rgba(102, 126, 234, 0.18);
  font-size: 10px;
}

.load-more-row {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 28px;
}

.load-more-btn {
  padding: 10px 32px;
  border: 1px solid var(--mp-line-strong);
  border-radius: 10px;
  color: var(--mp-text);
  background: var(--mp-panel);
  cursor: pointer;
  transition: all 0.2s ease;
}

.load-more-btn:hover:not(:disabled) {
  border-color: rgba(102, 126, 234, 0.46);
  color: #b9c7ff;
  background: rgba(102, 126, 234, 0.12);
}

.load-more-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.load-more-info {
  color: var(--mp-text-muted);
  font-size: 12px;
}

.detail-drawer {
  position: fixed;
  z-index: 60;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(560px, 100vw);
  overflow-y: auto;
  background: linear-gradient(180deg, rgba(11, 17, 19, 0.98), rgba(5, 8, 10, 0.99));
  border-left: 1px solid var(--mp-line);
  box-shadow: -24px 0 60px rgba(0, 0, 0, 0.5);
}

.drawer-close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  color: var(--mp-text);
  font-size: 24px;
  background: rgba(0, 0, 0, 0.6);
  cursor: pointer;
}

.detail-loading {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--mp-text-soft);
  font-size: 14px;
}

.detail-backdrop {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.detail-body {
  padding: 20px 24px 32px;
}

.detail-body h2 {
  margin: 0 0 4px;
  color: var(--mp-text);
  font-size: 22px;
}

.detail-original {
  margin: 0 0 12px;
  color: var(--mp-text-soft);
  font-size: 13px;
  font-style: italic;
}

.detail-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 0 0 14px;
  color: var(--mp-text-soft);
  font-size: 13px;
}

.detail-genres {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 16px;
}

.genre-tag {
  padding: 4px 10px;
  border-radius: 999px;
  color: #b9c7ff;
  background: rgba(102, 126, 234, 0.16);
  font-size: 12px;
}

.detail-overview {
  margin: 0;
  color: var(--mp-text-soft);
  font-size: 14px;
  line-height: 1.7;
}

.detail-overview.empty {
  color: var(--mp-text-muted);
}

.detail-actions-row {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
.wishlist-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border: 1px solid var(--mp-line);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--mp-text-soft);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: 0.18s ease;
}
.wishlist-btn:hover:not(:disabled) {
  border-color: rgba(255, 99, 132, 0.6);
  color: #ff7b95;
}
.wishlist-btn.active {
  background: rgba(255, 99, 132, 0.16);
  border-color: rgba(255, 99, 132, 0.5);
  color: #ff7b95;
}
.wishlist-icon { font-size: 15px; line-height: 1; }

.detail-similar {
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid var(--mp-line);
}
.similar-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: var(--mp-text);
}
.similar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 10px;
}
.similar-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: inherit;
}
.similar-card img {
  width: 100%;
  aspect-ratio: 2 / 3;
  object-fit: cover;
  border-radius: 6px;
  background: var(--mp-panel-deep);
}
.similar-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.similar-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--mp-text);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.similar-meta {
  font-size: 11px;
  color: var(--mp-text-muted);
}

.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.25s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
}

@media (max-width: 760px) {
  .pool-page {
    padding: 16px 14px 42px;
  }

  .pool-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .theater-topbar {
    flex-direction: column;
    align-items: stretch;
  }

  .pool-grid {
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 12px;
  }

  .detail-drawer {
    width: 100vw;
  }
}
</style>
