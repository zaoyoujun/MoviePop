/**
 * 影视详情页
 *
 * 页面结构：
 * 1. Hero 背景层 - 全屏横版海报背景
 * 2. Hero 内容层 - 标题、播放按钮居中叠加
 * 3. 信息内容层 - 左侧简介+剧集，右侧详细信息
 *
 * 使用组件：
 * - DetailEpisodes: 剧集选择组件
 * - DetailRecommend: 相关推荐组件
 */
<template>
  <main class="detail-page" :class="{ 'page-visible': pageVisible }" :style="detailThemeStyle">
    <!-- ==================== Hero 背景层 ==================== -->
    <section class="hero">
      <div class="hero-bg" :class="{ 'hero-bg-blur': !hasBackdrop }">
        <img :src="heroImage" alt="背景" />
      </div>
      <div class="hero-mask"></div>

      <!-- ==================== Hero 内容层 ==================== -->
      <div class="hero-center">
        <button class="back-btn" @click="goBack">
          <n-icon size="20"><ChevronBack /></n-icon>
          <span>返回</span>
        </button>
        
        <h1 class="hero-title">{{ activeHero.title }}</h1>
        
        <div class="hero-meta" v-if="activeHero.year || activeHero.rating">
          <span v-if="activeHero.year">{{ activeHero.year }}</span>
          <span v-if="activeHero.rating" class="hero-rating">
            <n-icon size="14"><Star /></n-icon>
            {{ activeHero.rating }}
          </span>
        </div>

        <n-button
          type="primary"
          size="large"
          class="btn-play"
          @click="handlePlay"
          :loading="isPlaying"
        >
          <template #icon>
            <n-icon><Play /></n-icon>
          </template>
          立即播放
        </n-button>
      </div>
    </section>

    <!-- ==================== 信息内容层 ==================== -->
    <section class="detail-content">
      <!-- 操作按钮 -->
      <div class="detail-actions">
        <n-button ghost class="action-btn" @click="handleFavorite">
          <template #icon>
            <n-icon><Heart /></n-icon>
          </template>
          {{ isFavorite ? '已收藏' : '收藏' }}
        </n-button>
        <n-button ghost class="action-btn">
          <template #icon>
            <n-icon><ImageOutline /></n-icon>
          </template>
          {{ detail.category || '分类' }}
        </n-button>
        <n-button ghost class="action-btn" @click="handleScrape">
          <template #icon>
            <n-icon><SearchOutline /></n-icon>
          </template>
          手动匹配
        </n-button>
      </div>

      <div class="content-grid">
        <!-- 左侧：简介 + 剧集 -->
        <div class="content-left">
          <!-- 简介 -->
          <div class="section">
            <h2 class="section-title">简介</h2>
            <p class="description">{{ activeHero.description || '暂无简介' }}</p>
          </div>

          <!-- 竖版海报 -->
          <div v-if="activeHero.poster" class="poster-small">
            <img :src="activeHero.poster" :alt="activeHero.title" />
          </div>
          <DetailEpisodes
            v-if="detail.versions?.length > 0 || detail.seasons?.length > 0"
            v-model="currentVersion"
            :versions="detail.versions"
            :media-versions="detail.mediaVersions"
            :seasons="detail.seasons"
            :fallback-image="activeHero.backdrop || activeHero.poster || heroImage"
            @play="handleVersionPlay"
          />

          <!-- 季选择与集数列表 -->
        </div>

        <!-- 右侧：详细信息 -->
        <div class="content-right">
          <div class="info-card">
            <!-- 原标题 -->
            <div v-if="detail.originalTitle" class="info-item">
              <span class="info-label">原标题</span>
              <span class="info-value">{{ detail.originalTitle }}</span>
            </div>

            <!-- 类型 -->
            <div v-if="genresList.length" class="info-item">
              <span class="info-label">类型</span>
              <div class="info-tags">
                <n-tag v-for="tag in genresList" :key="tag" round>{{ tag }}</n-tag>
              </div>
            </div>

            <!-- 标签 -->
            <div v-if="tagsList.length" class="info-item">
              <span class="info-label">风格/标签</span>
              <div class="info-tags">
                <n-tag v-for="tag in tagsList" :key="tag" round>{{ tag }}</n-tag>
              </div>
            </div>

            <!-- 国家/地区 -->
            <div v-if="countriesList.length" class="info-item">
              <span class="info-label">国家/地区</span>
              <span class="info-value">{{ countriesList.join(' / ') }}</span>
            </div>

            <!-- 年份 -->
            <div v-if="detail.year" class="info-item">
              <span class="info-label">年份</span>
              <span class="info-value">{{ detail.year }}</span>
            </div>

            <!-- 时长 -->
            <div v-if="detail.duration" class="info-item">
              <span class="info-label">时长</span>
              <span class="info-value">{{ detail.duration }}</span>
            </div>

            <!-- 评分 -->
            <div v-if="detail.rating" class="info-item">
              <span class="info-label">评分</span>
              <span class="info-value rating">
                <n-icon size="16"><Star /></n-icon>
                {{ detail.rating }}
              </span>
            </div>

            <!-- 语言 -->
            <div v-if="languagesList.length" class="info-item">
              <span class="info-label">语言</span>
              <span class="info-value">{{ languagesList.join(' / ') }}</span>
            </div>

            <!-- 元数据来源 -->
            <div v-if="detail.metadataSource" class="info-item">
              <span class="info-label">元数据来源</span>
              <span class="info-value">{{ detail.metadataSource }}</span>
            </div>

            <!-- 锁定状态 -->
            <div class="info-item">
              <span class="info-label">自定义资料</span>
              <div class="lock-status">
                <n-switch v-model:value="detail.metadataLocked" @update:value="handleLockChange" />
                <span>{{ detail.metadataLocked ? '已锁定' : '未锁定' }}</span>
              </div>
            </div>
          </div>

          <!-- 文件信息 -->
          <div class="info-card">
            <h3 class="card-title">文件信息</h3>
            <div v-if="detail.filePath" class="info-item">
              <span class="info-label">路径</span>
              <span class="info-value text-truncate">{{ detail.filePath }}</span>
            </div>
            <div v-if="detail.fileSize" class="info-item">
              <span class="info-label">大小</span>
              <span class="info-value">{{ detail.fileSize }}</span>
            </div>
            <div v-if="detail.quality" class="info-item">
              <span class="info-label">画质</span>
              <span class="info-value">{{ detail.quality }}</span>
            </div>
            <div v-if="detail.subtitle" class="info-item">
              <span class="info-label">字幕</span>
              <span class="info-value">{{ detail.subtitle }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 相关推荐 -->
      <DetailRecommend
        :movies="relatedMovies"
        @select="goDetail"
      />
    </section>

    <!-- ==================== 提示消息 ==================== -->
    <n-alert v-if="showTip" type="info" class="tip-alert" :bordered="false">
      {{ tipMessage }}
    </n-alert>

    <!-- ==================== 刮削弹窗 ==================== -->
    <Scrape
      :visible="showScrapeModal"
      :movie-id="detail.id"
      :metadata-locked="detail.metadataLocked || false"
      @close="showScrapeModal = false"
      @success="handleScrapeSuccess"
    />
  </main>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronBack,
  Star,
  Play,
  Heart,
  ImageOutline,
  SearchOutline
} from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'

import DetailEpisodes from '@/components/detail/DetailEpisodes.vue'
import DetailRecommend from '@/components/detail/DetailRecommend.vue'
import Scrape from './Scrape.vue'

import { startPlay } from '@/composables/usePlayer'
import { addFavorite, getRecommendations, removeFavorite } from '@/api/movie'
import { apiUrl } from '@/api/request'

const route = useRoute()
const router = useRouter()

const isFavorite = ref(false)
const showScrapeModal = ref(false)
const currentVersion = ref(0)
const showTip = ref(false)
const tipMessage = ref('')
const isPlaying = ref(false)
const pageVisible = ref(false)
const themePalette = ref({
  wash: 'rgba(99, 102, 241, 0.24)',
  mid: 'rgba(43, 39, 68, 0.92)',
  midSoft: 'rgba(43, 39, 68, 0.58)',
  base: '#151318',
  baseSoft: 'rgba(21, 19, 24, 0.88)',
  glow: 'rgba(99, 102, 241, 0.18)',
  line: 'rgba(140, 148, 210, 0.18)',
  chip: 'rgba(140, 148, 210, 0.2)'
})
let paletteRequestId = 0

const mockMovies = {
  'movie-1': {
    id: 'movie-1',
    title: '雪境来信',
    type: 'movie',
    year: 2024,
    originalTitle: 'Snow Letter',
    country: '日本',
    countries: ['日本'],
    duration: '128分钟',
    durationText: '128分钟',
    rating: 8.9,
    score: 8.9,
    tags: ['动漫', '治愈', '奇幻'],
    genres: ['动画', '奇幻'],
    languages: ['日语'],
    description: '在遥远的北方雪国，有一个神秘的传说。当雪花飘落时，会有一封信从天空飘来，带着远方的思念。主人公小雪意外获得了这封神秘的信件，由此展开了一段关于友情、成长和寻找自我的温暖旅程。',
    backdropUrl: 'https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=1920&q=80',
    coverUrl: 'https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=400&q=80',
    filePath: '/阿里云盘/动漫/雪境来信.mkv',
    fileSize: '2.4 GB',
    quality: '1080P · 立体声',
    subtitle: '内置中文字幕',
    lastPlayed: '2026-06-10 20:30',
    progress: { percent: 68 },
    category: '动漫',
    metadataSource: 'TMDB',
    metadataLocked: false
  },
  'movie-2': {
    id: 'movie-2',
    title: '蓝色边界',
    type: 'movie',
    year: 2022,
    originalTitle: 'Blue Boundary',
    country: '美国',
    countries: ['美国'],
    duration: '142分钟',
    durationText: '142分钟',
    rating: 8.5,
    score: 8.5,
    tags: ['电影', '剧情', '悬疑'],
    genres: ['剧情', '悬疑'],
    languages: ['英语'],
    description: '一段跨越三十年的秘密，一次改变命运的相遇。当真相浮出水面时，所有人都将面对自己内心深处的蓝色边界。这是一部关于救赎、原谅与人性的深刻作品。',
    backdropUrl: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=1920&q=80',
    coverUrl: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&q=80',
    filePath: '/NAS/电影/蓝色边界.mkv',
    fileSize: '8.2 GB',
    quality: '4K HDR · 5.1声道',
    subtitle: '中英双语字幕',
    lastPlayed: '2026-06-08 21:15',
    progress: { percent: 45 },
    category: '电影',
    metadataSource: 'TMDB',
    metadataLocked: false
  },
  'movie-3': {
    id: 'movie-3',
    title: '城市回声',
    type: 'series',
    year: 2021,
    originalTitle: 'City Echo',
    country: '中国',
    countries: ['中国'],
    duration: '单集45分钟',
    durationText: '45分钟',
    rating: 8.2,
    score: 8.2,
    tags: ['剧集', '都市', '情感'],
    genres: ['剧情', '爱情'],
    languages: ['中文'],
    description: '在繁华的都市中，每个人都有自己的故事。这部剧讲述了生活在同一栋公寓里的几个年轻人，在追逐梦想的过程中，相互扶持、共同成长的温暖故事。',
    backdropUrl: 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1920&q=80',
    coverUrl: 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=400&q=80',
    filePath: '/阿里云盘/剧集/城市回声/',
    fileSize: '48.6 GB',
    quality: '1080P · 立体声',
    subtitle: '内置中文字幕',
    lastPlayed: '2026-06-11 20:00',
    progress: { percent: 72 },
    category: '剧集',
    metadataSource: 'TMDB',
    metadataLocked: false,
    seasons: [
      {
        episodes: [
          { num: 1, title: '初到城市', episodeNumber: 1, id: 'ep1' },
          { num: 2, title: '新的开始', episodeNumber: 2, id: 'ep2' },
          { num: 3, title: '职场挑战', episodeNumber: 3, id: 'ep3' },
          { num: 4, title: '友谊萌芽', episodeNumber: 4, id: 'ep4' },
          { num: 5, title: '意外相遇', episodeNumber: 5, id: 'ep5' },
          { num: 6, title: '误会解开', episodeNumber: 6, id: 'ep6' },
          { num: 7, title: '共同成长', episodeNumber: 7, id: 'ep7' },
          { num: 8, title: '梦想起航', episodeNumber: 8, id: 'ep8' },
          { num: 9, title: '前路漫漫', episodeNumber: 9, id: 'ep9' },
          { num: 10, title: '春暖花开', episodeNumber: 10, id: 'ep10' }
        ]
      }
    ]
  },
  'default': {
    id: 'default',
    title: '星际穿越',
    type: 'series',
    year: 2014,
    originalTitle: 'Interstellar',
    country: '美国',
    countries: ['美国'],
    duration: '169分钟',
    durationText: '169分钟',
    rating: 9.5,
    score: 9.5,
    tags: ['科幻', '冒险', '诺兰'],
    genres: ['科幻', '冒险', '剧情'],
    languages: ['英语'],
    description: '不远的未来，地球气候已经不适合人类生存。一队探险家承担了人类历史上最重要的任务：穿越虫洞，穿越星际，去寻找适合人类居住的新家园。克里斯托弗·诺兰执导的经典神作，关于父爱、时空与人类文明的终极浪漫。',
    backdropUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1920&q=80',
    coverUrl: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=400&q=80',
    filePath: '/本地磁盘/影视/科幻/星际穿越.mkv',
    fileSize: '18.4 GB',
    quality: '4K HDR · 5.1声道',
    subtitle: '内置中英双语字幕',
    lastPlayed: '2026-05-15 20:30',
    progress: { percent: 78 },
    category: '电影',
    metadataSource: 'TMDB',
    metadataLocked: false,
    seasons: [
      {
        episodes: Array.from({ length: 12 }, (_, i) => ({
          num: i + 1,
          title: `第 ${i + 1} 集`,
          episodeNumber: i + 1,
          id: `ep${i + 1}`
        }))
      }
    ]
  }
}

const relatedMovies = ref([])

function normalizeRecommendItem(item) {
  const category = item.category || '电影'
  const genres = Array.isArray(item.genres) ? item.genres : []
  return {
    id: item.id,
    title: item.title || '未命名',
    year: item.year || '',
    category: category === 'movie' && genres.length ? genres[0] : category,
    rating: item.score || item.rating || '',
    poster: item.coverUrl || item.posterUrl || item.poster || ''
  }
}

const detail = ref(mockMovies['default'])
const loading = ref(false)
const loadError = ref('')

async function fetchDetail() {
  const id = route.params.id
  if (!id) return

  loading.value = true
  loadError.value = ''
  relatedMovies.value = []

  try {
    const response = await fetch(apiUrl(`/movies/${id}`))
    if (response.ok) {
      const result = await response.json()
      if (result.code === 0 && result.data) {
        detail.value = normalizeDetail(result.data)
        isFavorite.value = detail.value.isFavorite || false

        try {
          const recommendations = await getRecommendations(id, 8)
          relatedMovies.value = Array.isArray(recommendations)
            ? recommendations.map(normalizeRecommendItem)
            : []
        } catch (err) {
          console.error('[MovieDetail] 推荐加载失败:', err)
          relatedMovies.value = []
        }
        return
      }
    }
  } catch (err) {
    console.error('[MovieDetail] API 不可用:', err)
  } finally {
    loading.value = false
  }

  detail.value = normalizeDetail(mockMovies[id] || mockMovies['default'])
  relatedMovies.value = []
}

function normalizeDetail(data) {
  const rawCategory = (data.type || data.category || '').toString().toLowerCase()
  const isSeries = ['series', 'anime', '动漫', '电视剧', '剧集', 'tv'].includes(rawCategory)

  const playbackMap = {}
  const episodeProgress = data.playback?.episodeProgress || []
  episodeProgress.forEach(p => {
    const key = p.episodeId || `ep${p.episodeNumber || 0}`
    playbackMap[key] = p
  })

  const normalizeEpisodes = episodes => (episodes || []).map(ep => {
    const epNum = ep.episodeNumber || ep.num || 0
    const epId = ep.id || ep.episodeId || `ep${epNum}`
    const playback = playbackMap[epId] || playbackMap[`ep${epNum}`] || {}
    const percent = playback.percent || 0
    const watched = percent >= 90
    return {
      num: epNum,
      title: ep.title || `第 ${epNum} 集`,
      episodeId: epId,
      movieId: ep.movieId || data.id,
      watched,
      progress: percent,
      episodeNumber: epNum
    }
  })

  const versions = []
  if (data.seasons && Array.isArray(data.seasons) && data.seasons.length) {
    data.seasons.forEach((season, idx) => {
      versions.push({
        id: season.id,
        movieId: season.movieId || data.id,
        name: season.name || season.title || season.seasonTitle || `第${idx + 1}季`,
        displayTitle: season.displayTitle || season.title || season.name || '',
        description: season.description || '',
        score: season.score || 0,
        year: season.year || '',
        tags: season.tags || [],
        coverUrl: season.coverUrl || '',
        backdropUrl: season.backdropUrl || season.coverUrl || '',
        versionTitle: season.versionTitle || '',
        episodes: normalizeEpisodes(season.episodes)
      })
    })
  } else if (data.episodes && Array.isArray(data.episodes)) {
    versions.push({
      name: '原版',
      movieId: data.id,
      versionTitle: '',
      episodes: normalizeEpisodes(data.episodes)
    })
  }

  const mediaVersions = Array.isArray(data.versions) && data.versions.length > 1
    ? data.versions.map(v => ({
      name: v.name || v.title || v.versionName || v.seasonTitle || '版本',
      versionTitle: v.versionTitle || '',
      movieId: v.movieId || v.seasons?.[0]?.movieId || '',
      seasons: Array.isArray(v.seasons) ? v.seasons : []
    }))
    : []

  const tags = Array.isArray(data.tags) ? data.tags : []
  const genres = Array.isArray(data.genres) ? data.genres : []
  const countries = Array.isArray(data.countries) ? data.countries : (data.country ? [data.country] : [])
  const languages = Array.isArray(data.languages) ? data.languages : []

  return {
    id: data.id,
    title: data.title || '未命名影片',
    originalTitle: data.originalTitle || '',
    type: isSeries ? 'series' : 'movie',
    year: data.year || '',
    country: data.country || '',
    countries,
    duration: data.durationText || data.duration || '',
    durationText: data.durationText || '',
    rating: data.score || data.rating || 0,
    score: data.score || 0,
    tags,
    genres,
    languages,
    description: data.description || '',
    backdrop: data.backdropUrl || data.coverUrl || '',
    poster: data.coverUrl || '',
    backdropUrl: data.backdropUrl || '',
    coverUrl: data.coverUrl || '',
    filePath: data.filePath || '',
    fileSize: data.fileSize || '',
    quality: data.quality || '',
    subtitle: data.subtitle || '',
    lastPlayed: data.lastPlayed || '',
    progress: data.progress || { percent: 0 },
    category: data.category,
    isFavorite: data.isFavorite || false,
    metadataSource: data.metadataSource || '',
    metadataLocked: data.metadataLocked || false,
    versions,
    mediaVersions
  }
}

watch(() => route.params.id, () => { fetchDetail() }, { immediate: true })

// 资源库扫描完成后，如果当前在详情页，自动刷新详情
function handleScanCompleted() {
  fetchDetail()
}

onMounted(() => {
  window.addEventListener('scan:completed', handleScanCompleted)
})

onUnmounted(() => {
  window.removeEventListener('scan:completed', handleScanCompleted)
})

const heroImage = computed(() => {
  return activeHero.value.backdrop || activeHero.value.backdropUrl || detail.value.backdropUrl || detail.value.coverUrl || ''
})

const hasBackdrop = computed(() => {
  return !!detail.value.backdropUrl
})

const contentGradient = computed(() => {
  const palette = themePalette.value
  return [
    `radial-gradient(circle at 18% 0%, ${palette.glow}, transparent 34%)`,
    `radial-gradient(circle at 78% 8%, ${palette.wash}, transparent 30%)`,
    `linear-gradient(to bottom, ${palette.wash} 0%, ${palette.mid} 30%, ${palette.base} 72%)`
  ].join(', ')

  const category = (detail.value.category || '').toLowerCase()
  if (['anime', '动漫', '动画'].includes(category)) {
    return 'linear-gradient(to bottom, rgba(66, 103, 178, 0.18), rgba(21, 19, 24, 0.95) 45%, #151318 70%)'
  }
  if (['movie', '电影'].includes(category)) {
    return 'linear-gradient(to bottom, rgba(42, 42, 42, 0.25), rgba(21, 19, 24, 0.95) 40%, #151318 65%)'
  }
  if (['series', 'tv', '电视剧', '剧集'].includes(category)) {
    return 'linear-gradient(to bottom, rgba(46, 139, 87, 0.15), rgba(21, 19, 24, 0.95) 45%, #151318 70%)'
  }
  return 'linear-gradient(to bottom, rgba(21, 19, 24, 0.72), #151318 34%)'
})

const detailThemeStyle = computed(() => {
  const palette = themePalette.value
  return {
    '--detail-wash': palette.wash,
    '--detail-glow': palette.glow,
    '--detail-mid': palette.mid,
    '--detail-mid-soft': palette.midSoft,
    '--detail-base': palette.base,
    '--detail-base-soft': palette.baseSoft,
    '--detail-line': palette.line,
    '--detail-chip': palette.chip
  }
})

const activeChapter = computed(() => {
  return detail.value.versions?.[currentVersion.value] || null
})

const activeHero = computed(() => {
  const chapter = activeChapter.value
  if (!chapter) return detail.value
  return {
    ...detail.value,
    title: chapter.displayTitle || detail.value.title,
    year: chapter.year || detail.value.year,
    rating: chapter.score || detail.value.rating,
    tags: chapter.tags?.length ? chapter.tags : detail.value.tags,
    description: chapter.description || detail.value.description,
    backdrop: chapter.backdropUrl || chapter.coverUrl || detail.value.backdrop,
    poster: chapter.coverUrl || detail.value.poster
  }
})

const genresList = computed(() => {
  const set = new Set([...(detail.value.genres || []), ...(activeHero.value.tags || [])])
  return Array.from(set).slice(0, 8)
})

const tagsList = computed(() => {
  const allTags = [...(detail.value.tags || []), ...(activeHero.value.tags || [])]
  const set = new Set(allTags.filter(t => !genresList.value.includes(t)))
  return Array.from(set).slice(0, 8)
})

const countriesList = computed(() => {
  return [...new Set(detail.value.countries || [])]
})

const languagesList = computed(() => {
  return [...new Set(detail.value.languages || [])]
})

watch(heroImage, (imageUrl) => {
  updateThemePalette(imageUrl)
}, { immediate: true })

async function updateThemePalette(imageUrl) {
  const requestId = ++paletteRequestId
  const fallback = paletteFromString(imageUrl || detail.value.title || 'moviepop')
  themePalette.value = buildPalette(fallback)

  if (!imageUrl) return

  try {
    const color = await extractImageColor(imageUrl)
    if (requestId === paletteRequestId && color) {
      themePalette.value = buildPalette(color)
    }
  } catch (err) {
    if (requestId === paletteRequestId) {
      themePalette.value = buildPalette(fallback)
    }
  }
}

function extractImageColor(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.decoding = 'async'
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        const width = 72
        const height = 40
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        ctx.drawImage(img, 0, 0, width, height)
        const data = ctx.getImageData(0, 0, width, height).data
        let r = 0
        let g = 0
        let b = 0
        let total = 0

        for (let i = 0; i < data.length; i += 16) {
          const red = data[i]
          const green = data[i + 1]
          const blue = data[i + 2]
          const alpha = data[i + 3]
          if (alpha < 200) continue
          const max = Math.max(red, green, blue)
          const min = Math.min(red, green, blue)
          const luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
          const saturation = max === 0 ? 0 : (max - min) / max
          if (luminance < 0.08 || luminance > 0.92) continue
          const weight = 0.35 + saturation * 1.7 + Math.min(luminance, 0.72)
          r += red * weight
          g += green * weight
          b += blue * weight
          total += weight
        }

        if (!total) {
          reject(new Error('no usable pixels'))
          return
        }

        resolve({
          r: Math.round(r / total),
          g: Math.round(g / total),
          b: Math.round(b / total)
        })
      } catch (err) {
        reject(err)
      }
    }
    img.onerror = reject
    img.src = src
  })
}

function paletteFromString(value) {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0
  }
  return hslToRgb(Math.abs(hash) % 360, 58, 46)
}

function buildPalette(color) {
  const hsl = rgbToHsl(color.r, color.g, color.b)
  const saturation = Math.max(24, Math.min(64, hsl.s + 12))
  const accent = hslToRgb(hsl.h, Math.min(76, saturation + 8), Math.min(54, Math.max(30, hsl.l + 4)))
  const mid = hslToRgb(hsl.h, Math.min(52, saturation), 14)
  const base = hslToRgb(hsl.h, Math.min(46, saturation), 7)
  const line = hslToRgb(hsl.h, Math.min(44, saturation), 38)
  return {
    wash: rgba(accent, 0.3),
    mid: rgba(mid, 0.78),
    midSoft: rgba(mid, 0.58),
    base: rgb(base),
    baseSoft: rgba(base, 0.88),
    glow: rgba(accent, 0.2),
    line: rgba(line, 0.18),
    chip: rgba(line, 0.2)
  }
}

function rgbToHsl(r, g, b) {
  r /= 255
  g /= 255
  b /= 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let h = 0
  let s = 0
  const l = (max + min) / 2

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
    h /= 6
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100)
  }
}

function hslToRgb(h, s, l) {
  s /= 100
  l /= 100
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h / 60) % 2 - 1))
  const m = l - c / 2
  let r = 0
  let g = 0
  let b = 0

  if (h < 60) [r, g, b] = [c, x, 0]
  else if (h < 120) [r, g, b] = [x, c, 0]
  else if (h < 180) [r, g, b] = [0, c, x]
  else if (h < 240) [r, g, b] = [0, x, c]
  else if (h < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]

  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255)
  }
}

function rgb(color) {
  return `rgb(${color.r}, ${color.g}, ${color.b})`
}

function rgba(color, alpha) {
  return `rgba(${color.r}, ${color.g}, ${color.b}, ${alpha})`
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/home')
  }
}

function handlePlay() {
  if (isPlaying.value) {
    showTipMessage('正在播放中，请稍候...')
    return
  }

  const d = detail.value
  if (!d?.id) {
    showTipMessage('影片信息尚未加载完成')
    return
  }

  isPlaying.value = true

  if (d.type === 'series') {
    const currentVersionEpisodes = d.versions?.[currentVersion.value]?.episodes || []
    const ep = currentVersionEpisodes.find(e => e.progress < 90 && e.progress > 0) || currentVersionEpisodes[0]
    
    if (!ep) {
      const fallbackEpisodes = Array.isArray(d.episodes) ? d.episodes : []
      const fallbackEp = fallbackEpisodes.find(e => e.progress < 90 && e.progress > 0) || fallbackEpisodes[0]
      if (!fallbackEp) {
        showTipMessage('当前版本暂无可播放剧集')
        isPlaying.value = false
        return
      }
      doPlayEpisode(fallbackEp, currentVersion.value)
    } else {
      doPlayEpisode(ep, currentVersion.value)
    }
  } else {
    doPlayMovie(d)
  }

  setTimeout(() => { isPlaying.value = false }, 3000)
}

function handleVersionPlay(episode) {
  if (isPlaying.value) {
    showTipMessage('正在播放中，请稍候...')
    return
  }

  const d = detail.value
  if (!d?.id) {
    showTipMessage('影片信息尚未加载完成')
    return
  }

  isPlaying.value = true

  const versionIdx = episode.version || 0
  const versionEpisodes = d.versions?.[versionIdx]?.episodes || []
  let ep = versionEpisodes.find(e => e.num === episode.episode) || versionEpisodes[episode.episode - 1]
  
  if (!ep) {
    const fallbackEpisodes = Array.isArray(d.episodes) ? d.episodes : []
    ep = fallbackEpisodes.find(e => e.num === episode.episode) || fallbackEpisodes[episode.episode - 1]
    if (!ep) {
      showTipMessage('找不到对应剧集')
      isPlaying.value = false
      return
    }
  }
  doPlayEpisode(ep, versionIdx)

  setTimeout(() => { isPlaying.value = false }, 3000)
}

function doPlayMovie(d) {
  startPlay({
    movieId: d.id,
    movieTitle: d.title,
    episodeId: '',
    episodeTitle: '',
    cover: d.poster || d.backdrop || '',
    episodeList: [],
    seasonIndex: 0
  })
}

function doPlayEpisode(ep, versionIdx) {
  const d = detail.value
  let versionEpisodes = d.versions?.[versionIdx]?.episodes || []
  if (!versionEpisodes.length && Array.isArray(d.episodes)) {
    versionEpisodes = d.episodes
  }
  const episodeList = versionEpisodes.map(e => ({
    id: e.episodeId || `${d.id}_ep${e.num}`,
    movieId: e.movieId || d.id,
    title: e.title || `第 ${e.num} 集`,
    num: e.num
  }))
  const epId = ep.episodeId

  startPlay({
    movieId: ep.movieId || d.id,
    movieTitle: d.title,
    episodeId: epId,
    episodeTitle: ep.title || `第 ${ep.num} 集`,
    cover: d.poster || d.backdrop || '',
    episodeList,
    seasonIndex: versionIdx
  })
}

function showTipMessage(message) {
  tipMessage.value = message
  showTip.value = true
  setTimeout(() => { showTip.value = false }, 3000)
}

async function handleFavorite() {
  const newFavorite = !isFavorite.value
  try {
    if (newFavorite) {
      await addFavorite(detail.value.id)
    } else {
      await removeFavorite(detail.value.id)
    }
    isFavorite.value = newFavorite
    showTip.value = true
    tipMessage.value = isFavorite.value ? '已添加到收藏' : '已取消收藏'
    setTimeout(() => { showTip.value = false }, 3000)
  } catch (error) {
    showTip.value = true
    tipMessage.value = newFavorite ? '添加收藏失败' : '取消收藏失败'
    setTimeout(() => { showTip.value = false }, 3000)
  }
}

async function handleLockChange(locked) {
  try {
    const response = await fetch(
      apiUrl(`/movies/${detail.value.id}/metadata/lock`),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ locked })
      }
    )
    const res = await response.json()
    if (res.code !== 0) {
      detail.value.metadataLocked = !locked
      alert(res.message || '锁定操作失败')
    }
  } catch (error) {
    detail.value.metadataLocked = !locked
    alert('锁定操作失败：' + error.message)
  }
}

function handleScrape() {
  showScrapeModal.value = true
}

async function handleScrapeSuccess() {
  showTip.value = true
  tipMessage.value = '刮削成功'
  setTimeout(() => { showTip.value = false }, 3000)
  await fetchDetail()
}

function goDetail(id) {
  currentVersion.value = 0
  router.push({ name: 'MovieDetail', params: { id } })
}

onMounted(() => {
  setTimeout(() => { pageVisible.value = true }, 100)
})
</script>

<style scoped>
.detail-page {
  height: 100vh;
  min-height: 100vh;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  background:
    radial-gradient(circle at 50% 8%, var(--detail-glow), transparent 34%),
    linear-gradient(180deg, var(--detail-mid) 0%, var(--detail-base) 62%);
  color: #ffffff;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.5s ease, transform 0.5s ease;
}

.detail-page.page-visible {
  opacity: 1;
  transform: translateY(0);
}

.hero {
  position: relative;
  min-height: 62vh;
  max-height: 720px;
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.hero-bg img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center top;
}

.hero-bg-blur img {
  filter: blur(20px);
  transform: scale(1.1);
}

.hero-mask {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.04) 42%, rgba(0, 0, 0, 0.2) 62%, var(--detail-mid-soft) 84%, var(--detail-base) 100%),
    linear-gradient(90deg, rgba(0, 0, 0, 0.18), rgba(0, 0, 0, 0.02) 48%, rgba(0, 0, 0, 0.28));
}

.hero-center {
  position: absolute;
  inset: 0;
  z-index: 2;
  padding-bottom: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  text-align: center;
  color: #fff;
  text-shadow: 0 2px 14px rgba(0,0,0,.45);
}

.back-btn {
  position: absolute;
  top: 24px;
  left: 24px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  font-size: 14px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: rgba(0, 0, 0, 0.65);
  transform: translateX(-2px);
}

.hero-title {
  font-size: 48px;
  font-weight: 700;
  margin-bottom: 12px;
  line-height: 1.2;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  font-size: 16px;
  color: #a0a0b0;
}

.hero-rating {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #fbbf24;
  font-weight: 600;
}

.btn-play {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.74));
  border-color: rgba(255, 255, 255, 0.62);
  color: #121212;
  padding: 14px 32px;
  font-size: 16px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28);
}

.btn-play:hover {
  background: #ffffff;
  border-color: #ffffff;
}

.detail-content {
  position: relative;
  z-index: 3;
  margin-top: -72px;
  padding: 128px 7vw 96px;
  display: flex;
  flex-direction: column;
  gap: 48px;
  background:
    linear-gradient(180deg, transparent 0%, var(--detail-mid) 118px, var(--detail-base) 390px);
}

.detail-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
}

.action-btn {
  min-width: 120px;
  border-color: var(--detail-line);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 72px;
}

.content-left {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.description {
  font-size: 15px;
  line-height: 1.8;
  color: #d0d0e0;
  margin: 0;
}

.poster-small {
  width: 160px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.poster-small img {
  width: 100%;
  height: 230px;
  object-fit: cover;
}

.content-right {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.info-card {
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid var(--detail-line);
  border-radius: 16px;
  padding: 24px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
  backdrop-filter: blur(8px);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--detail-line);
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 13px;
  color: #7a7a8a;
  min-width: 80px;
}

.info-value {
  font-size: 14px;
  color: #e0e0f0;
  text-align: right;
  flex: 1;
}

.info-value.rating {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  color: #fbbf24;
}

.info-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  flex: 1;
}

.info-tags .n-tag {
  background: var(--detail-chip);
  border: 1px solid var(--detail-line);
  color: rgba(255, 255, 255, 0.88);
  font-size: 12px;
}

.lock-status {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: flex-end;
}

.lock-status span {
  font-size: 13px;
  color: #a0a0b0;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tip-alert {
  position: fixed;
  top: 80px;
  right: 20px;
  max-width: 360px;
  z-index: 1000;
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
    gap: 48px;
  }

  .poster-small {
    width: 140px;
  }

  .poster-small img {
    height: 200px;
  }
}

@media (max-width: 768px) {
  .detail-content {
    grid-template-columns: 1fr;
    gap: 32px;
    padding: 48px 20px 72px;
  }

  .hero {
    min-height: 52vh;
  }

  .hero-center {
    min-height: 52vh;
  }

  .hero-title {
    font-size: 32px;
  }

  .back-btn {
    top: 16px;
    left: 16px;
    padding: 6px 12px;
    font-size: 13px;
  }

  .detail-actions {
    gap: 12px;
  }

  .action-btn {
    min-width: 100px;
  }

  .poster-small {
    width: 120px;
  }

  .poster-small img {
    height: 175px;
  }
}
</style>
