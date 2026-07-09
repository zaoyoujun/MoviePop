<template>
  <main class="stats-page">
    <section class="stats-hero">
      <div>
        <span class="kicker">VIEWING INSIGHT</span>
        <h1>观影统计</h1>
        <p>基于片库、播放进度、收藏和观看时间生成你的私人影院画像。</p>
      </div>
      <button class="refresh-button" :disabled="loading" type="button" @click="loadStats">
        {{ loading ? '同步中' : '刷新' }}
      </button>
    </section>

    <section v-if="error" class="state-card error-card">
      {{ error }}
    </section>

    <section v-else-if="loading && !hasData" class="state-card">
      正在整理观影统计...
    </section>

    <template v-else>
      <section class="personality-card">
        <div class="personality-code" :style="personalityGradient">
          <strong>{{ isInsufficient ? 'XXX' : (personality.code || 'CINE') }}</strong>
          <span>{{ isInsufficient ? '未知因素' : (personality.title || '光影旅人') }}</span>
          <span class="confidence" v-if="!isInsufficient">{{ (personality.confidence || 0) }}% 置信度</span>
        </div>
        <div class="personality-copy">
          <h2>你的观影人格</h2>
          <p>{{ isInsufficient ? '样本积累中，继续观看解锁专属人格！' : (personality.description || '偏爱沉浸式长片和高完成度收藏，周末夜晚是你的主场。') }}</p>
          <div class="trait-list" v-if="!isInsufficient">
            <span v-for="trait in normalizedTraits" :key="trait">{{ trait }}</span>
          </div>
          <div class="trait-list insufficient-hint" v-else>
            <span>至少 5 部有效观看</span>
            <span>3 个活跃日</span>
            <span>累计观看 180 分钟</span>
          </div>
        </div>
        <div class="dimension-list" v-if="!isInsufficient">
          <div v-for="dim in normalizedDimensions" :key="dim.key" class="dimension-row">
            <div class="dimension-header">
              <strong>{{ getDimensionName(dim.key) }}</strong>
            </div>
            <div class="dimension-row-content">
              <div class="dimension-label-group">
                <span class="dimension-winner">{{ dim.leftCode || getFirstLetter(getLeftEnLabel(dim)) }}</span>
                <span class="dimension-label">{{ dim.left }}</span>
                <strong>{{ getLeftEnLabel(dim) }}</strong>
              </div>
              <div class="dimension-track">
                <i :style="getWaveStyle(dim)"></i>
              </div>
              <div class="dimension-label-group">
                <span class="dimension-winner">{{ dim.rightCode || getFirstLetter(getRightEnLabel(dim)) }}</span>
                <span class="dimension-label">{{ dim.right }}</span>
                <strong>{{ getRightEnLabel(dim) }}</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="metric-grid">
        <article v-for="metric in metrics" :key="metric.key || metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ formatMetric(metric.value) }}<small>{{ metric.unit }}</small></strong>
          <p>{{ metric.description }}</p>
        </article>
      </section>

      <section class="dashboard-grid">
        <article class="panel">
          <header>
            <h2>分类分布</h2>
            <span>{{ overview.total || 0 }} 个条目</span>
          </header>
          <div class="bar-list">
            <div v-for="item in categoryDistribution" :key="item.label" class="bar-row">
              <div class="row-head">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <div class="bar-track"><i :style="{ width: `${clampPercent(item.percent)}%` }"></i></div>
            </div>
          </div>
        </article>

        <article class="panel">
          <header>
            <h2>来源分布</h2>
            <span>本地 / WebDAV / OpenList</span>
          </header>
          <div class="source-list">
            <div v-for="item in sourceDistribution" :key="item.label" class="source-item">
              <div>
                <span>{{ item.label }}</span>
                <strong>{{ item.percent }}%</strong>
              </div>
              <div class="bar-track"><i :style="{ width: `${clampPercent(item.percent)}%` }"></i></div>
            </div>
          </div>
        </article>

        <article class="panel wide rhythm-panel">
          <header>
            <h2>24 小时观影节律</h2>
            <span>{{ peakHour }}</span>
          </header>
          <div class="clock-chart">
            <div class="clock-container">
              <div class="clock-face">
                <div
                  v-for="item in timeDistribution"
                  :key="item.hour"
                  class="clock-sector"
                  :class="{ 'has-data': item.value > 0 }"
                  :style="getClockSectorStyle(item)"
                ></div>
                <div class="clock-labels">
                  <span
                    v-for="item in timeDistribution"
                    :key="`label-${item.hour}`"
                    class="sector-label"
                    :style="getSectorLabelStyle(item)"
                  >{{ item.hour }}</span>
                </div>
              </div>
              <div class="clock-center">
                <div class="clock-hour-hand"></div>
                <div class="clock-minute-hand"></div>
                <span class="center-label">{{ peakHour?.replace('高峰 ', '') }}</span>
              </div>
            </div>
          </div>
        </article>

        <article class="panel">
          <header>
            <h2>完成状态</h2>
            <span>{{ overview.completionRate || 0 }}%</span>
          </header>
          <div class="completion-ring">
            <strong>{{ overview.completionRate || 82 }}%</strong>
            <span>已看完</span>
          </div>
          <div class="bar-list compact-list">
            <div v-for="item in completionStats" :key="item.label" class="bar-row">
              <div class="row-head">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <div class="bar-track"><i :style="{ width: `${clampPercent(item.percent)}%` }"></i></div>
            </div>
          </div>
        </article>

        <article class="panel">
          <header>
            <h2>偏好标签</h2>
            <span>类型 / 地区 / 标签</span>
          </header>
          <div class="tag-cloud">
            <span
              v-for="(item, index) in tagDistribution"
              :key="item.label"
              :style="getTagStyle(item.percent, index)"
            >
              <span>{{ item.label }}</span>
            </span>
          </div>
        </article>
      </section>

      <section class="history-panel">
        <header>
          <h2>最近观看</h2>
          <span>{{ recentHistory.length }} 条</span>
        </header>
        <div class="history-list">
          <article v-for="movie in recentHistory" :key="movie.id" class="history-card">
            <img :src="movie.coverUrl || movie.cover || fallbackCover" :alt="movie.title" class="card-image">
            <div class="card-bottom">
              <strong>{{ movie.title }}</strong>
              <span>{{ movie.category || '影视' }} / {{ getProgress(movie) }}%</span>
            </div>
          </article>
          <div v-if="!recentHistory.length" class="history-empty">暂无观看记录</div>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getStats } from '@/api/movie'
import { MOCK_DATA } from '@/api/mockData'

const loading = ref(false)
const error = ref('')
const stats = ref({})
const fallbackCover = 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&q=85'
const waveTime = ref(0)
const tagTime = ref(0)
let animationFrameId = null
const tagPhysics = ref([])

const hasData = computed(() => Object.keys(stats.value || {}).length > 0)
const overview = computed(() => stats.value.overview || fallbackStats.overview)
const metrics = computed(() => stats.value.metrics || fallbackStats.metrics)
const personality = computed(() => {
  const viewingPersonality = stats.value.viewingPersonality
  if (viewingPersonality && Object.keys(viewingPersonality).length > 0) {
    return viewingPersonality
  }
  return stats.value.personality || fallbackStats.personality
})
const normalizedTraits = computed(() => personality.value.traits?.length ? personality.value.traits : fallbackStats.personality.traits)
const normalizedDimensions = computed(() => personality.value.dimensions?.length ? personality.value.dimensions : fallbackStats.personality.dimensions)

const isInsufficient = computed(() => {
  const code = personality.value.code || ''
  return code.toLowerCase().includes('insufficient')
})

const dimensionNames = {
  concentration: '投入浓度',
  breadth: '内容视野',
  rhythm: '行为节律',
  pace: '投入浓度',
  taste: '内容视野',
  source: '行为节律',
  focus: '投入浓度',
  depth: '内容视野',
  routine: '行为节律'
}

const dimensionLabels = {
  concentration: { 'Focus': '聚焦型', 'Scattered': '碎片型', 'F': '聚焦型', 'S': '碎片型' },
  breadth: { 'Depth': '深耕型', 'Width': '泛览型', 'D': '深耕型', 'W': '泛览型' },
  rhythm: { 'Routine': '规律型', 'Casual': '随性型', 'R': '规律型', 'C': '随性型' },
  pace: { 'Focus': '聚焦型', 'Scattered': '碎片型', 'F': '聚焦型', 'S': '碎片型' },
  taste: { 'Depth': '深耕型', 'Width': '泛览型', 'D': '深耕型', 'W': '泛览型' },
  source: { 'Routine': '规律型', 'Casual': '随性型', 'R': '规律型', 'C': '随性型' },
  focus: { 'Focus': '聚焦型', 'Scattered': '碎片型', 'F': '聚焦型', 'S': '碎片型' },
  depth: { 'Depth': '深耕型', 'Width': '泛览型', 'D': '深耕型', 'W': '泛览型' },
  routine: { 'Routine': '规律型', 'Casual': '随性型', 'R': '规律型', 'C': '随性型' }
}

const chineseToEnLabels = {
  '碎片': 'Scattered',
  '聚焦': 'Focus',
  '泛览': 'Width',
  '深耕': 'Depth',
  '随性': 'Casual',
  '规律': 'Routine',
  'F': 'Focus',
  'S': 'Scattered',
  'W': 'Width',
  'D': 'Depth',
  'C': 'Casual',
  'R': 'Routine'
}

const singleLetterToFull = {
  'F': 'Focus',
  'S': 'Scattered',
  'W': 'Width',
  'D': 'Depth',
  'C': 'Casual',
  'R': 'Routine'
}

function getDimensionName(key) {
  return dimensionNames[key] || key
}

function getDimensionLabel(dim) {
  const labels = dimensionLabels[dim.key] || {}
  const winner = dim.winner || ''
  if (winner && labels[winner]) {
    return labels[winner]
  }
  if (winner && singleLetterToFull[winner]) {
    return labels[singleLetterToFull[winner]] || winner
  }
  const enLabel = chineseToEnLabels[dim.right] || chineseToEnLabels[dim.left] || winner
  const reverseLabels = Object.fromEntries(Object.entries(labels).map(([k, v]) => [v, k]))
  return reverseLabels[enLabel] || winner || ''
}

function getLeftEnLabel(dim) {
  if (dim.leftCode && singleLetterToFull[dim.leftCode]) {
    return singleLetterToFull[dim.leftCode]
  }
  if (dim.left && singleLetterToFull[dim.left]) {
    return singleLetterToFull[dim.left]
  }
  return chineseToEnLabels[dim.left] || dim.left || ''
}

function getRightEnLabel(dim) {
  if (dim.rightCode && singleLetterToFull[dim.rightCode]) {
    return singleLetterToFull[dim.rightCode]
  }
  if (dim.right && singleLetterToFull[dim.right]) {
    return singleLetterToFull[dim.right]
  }
  return chineseToEnLabels[dim.right] || dim.right || ''
}

function getFirstLetter(str) {
  return str ? str.charAt(0).toUpperCase() : ''
}

function getWaveStyle(dim) {
  const rightScore = clampPercent(dim.rightScore ?? dim.score ?? 50)
  const leftScore = clampPercent(dim.leftScore ?? 100 - rightScore)
  const peakPosition = rightScore
  const isRight = rightScore > leftScore
  const time = waveTime.value
  let path = '0% 50%'
  for (let i = 5; i <= 100; i += 5) {
    const distanceFromPeak = Math.abs(i - peakPosition) / 50
    const waveHeight = 25 * Math.exp(-distanceFromPeak * 1.2)
    const wavePhase = Math.sin(i * 0.3 + time * (isRight ? 1 : -1)) * 8
    const flowOffset = Math.sin(i * 0.15 + time * 2) * 4
    const y = 50 - waveHeight + wavePhase + flowOffset
    path += `, ${i}% ${y}%`
  }
  path += ', 100% 50%, 100% 100%, 0% 100%'
  const gradient = isRight
    ? 'linear-gradient(90deg, rgba(255, 255, 255, 0.15), rgba(102, 126, 234, 0.6), rgba(118, 75, 162, 0.8), rgba(0, 0, 0, 0.9))'
    : 'linear-gradient(90deg, rgba(0, 0, 0, 0.9), rgba(118, 75, 162, 0.8), rgba(102, 126, 234, 0.6), rgba(255, 255, 255, 0.15))'
  return {
    width: '100%',
    clipPath: `polygon(${path})`,
    background: gradient,
    backgroundSize: '100% 100%'
  }
}

function getClockSectorStyle(item) {
  const startAngle = (item.hour / 24) * 360 - 90
  const endAngle = ((item.hour + 1) / 24) * 360 - 90
  const percent = item.percent || 0
  const intensity = Math.max(0.06, Math.min(1, percent / 100))
  const radius = 96
  const innerRadius = 48

  function polar(angleDeg, r) {
    const rad = (angleDeg * Math.PI) / 180
    return {
      x: 100 + r * Math.cos(rad),
      y: 100 + r * Math.sin(rad)
    }
  }

  const startOuter = polar(startAngle, radius)
  const endOuter = polar(endAngle, radius)
  const startInner = polar(startAngle, innerRadius)
  const endInner = polar(endAngle, innerRadius)

  const largeArc = endAngle - startAngle > 180 ? 1 : 0
  const path = [
    `M ${startOuter.x} ${startOuter.y}`,
    `A ${radius} ${radius} 0 ${largeArc} 1 ${endOuter.x} ${endOuter.y}`,
    `L ${endInner.x} ${endInner.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${startInner.x} ${startInner.y}`,
    'Z'
  ].join(' ')

  return {
    clipPath: `path('${path}')`,
    background: `rgba(102, 126, 234, ${intensity})`,
    opacity: 0.95
  }
}

function getSectorLabelStyle(item) {
  const midAngle = ((item.hour + 0.5) / 24) * 360 - 90
  const radius = 72
  const x = 100 + radius * Math.cos((midAngle * Math.PI) / 180)
  const y = 100 + radius * Math.sin((midAngle * Math.PI) / 180)
  const percent = item.percent || 0
  return {
    left: `${x}px`,
    top: `${y}px`,
    color: percent > 35 ? 'rgba(255, 255, 255, 0.9)' : 'rgba(255, 255, 255, 0.5)'
  }
}

const gradientColors = [
  ['#667eea', '#764ba2'],
  ['#f093fb', '#f5576c'],
  ['#4facfe', '#00f2fe'],
  ['#43e97b', '#38f9d7'],
  ['#fa709a', '#fee140'],
  ['#a8edea', '#fed6e3'],
  ['#ff9a9e', '#fecfef'],
  ['#ffecd2', '#fcb69f']
]

const personalityGradient = computed(() => {
  const seed = String(personality.value.code || personality.value.title || 'CINE').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  const colors = gradientColors[seed % gradientColors.length]
  const opacity = 0.15 + Math.random() * 0.1
  return {
    background: `linear-gradient(135deg, ${colors[0]}${Math.round(opacity * 255).toString(16).padStart(2, '0')}, ${colors[1]}${Math.round(opacity * 255).toString(16).padStart(2, '0')})`,
    borderColor: `${colors[0]}40`
  }
})

const categoryDistribution = computed(() => stats.value.categoryDistribution?.length ? stats.value.categoryDistribution : fallbackStats.categoryDistribution)
const sourceDistribution = computed(() => stats.value.sourceDistribution?.length ? stats.value.sourceDistribution : fallbackStats.sourceDistribution)
const timeDistribution = computed(() => stats.value.timeDistribution?.length ? stats.value.timeDistribution : fallbackStats.timeDistribution)
const completionStats = computed(() => stats.value.completionStats?.length ? stats.value.completionStats : fallbackStats.completionStats)
const tagDistribution = computed(() => stats.value.tagDistribution?.length ? stats.value.tagDistribution : fallbackStats.tagDistribution)
const recentHistory = computed(() => stats.value.recentHistory?.length ? stats.value.recentHistory : fallbackStats.recentHistory)

const peakHour = computed(() => {
  const peak = [...timeDistribution.value].sort((a, b) => (b.value || 0) - (a.value || 0))[0]
  return peak && peak.value ? `高峰 ${String(peak.hour).padStart(2, '0')}:00` : '暂无观看时段'
})

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await getStats()
  } catch (err) {
    stats.value = fallbackStats
    error.value = ''
  } finally {
    loading.value = false
    const tags = tagDistribution.value
    if (tags && tags.length > 0) {
      initTagPhysics(tags.length)
    }
  }
}

function clampPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 0
  return Math.max(0, Math.min(100, number))
}

function formatMetric(value) {
  if (typeof value === 'number' && !Number.isInteger(value)) {
    return value.toFixed(1)
  }
  return value ?? 0
}

function tagSize(percent) {
  return `${12 + clampPercent(percent) * 0.14}px`
}

const tagColors = [
  { bg: 'rgba(102, 126, 234, 0.3)', text: '#818cf8', border: 'rgba(102, 126, 234, 0.5)' },
  { bg: 'rgba(118, 75, 162, 0.3)', text: '#a78bfa', border: 'rgba(118, 75, 162, 0.5)' },
  { bg: 'rgba(91, 192, 241, 0.3)', text: '#60a5fa', border: 'rgba(91, 192, 241, 0.5)' },
  { bg: 'rgba(167, 139, 250, 0.3)', text: '#c4b5fd', border: 'rgba(167, 139, 250, 0.5)' },
  { bg: 'rgba(56, 189, 248, 0.3)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.5)' },
  { bg: 'rgba(139, 92, 246, 0.3)', text: '#a78bfa', border: 'rgba(139, 92, 246, 0.5)' }
]

function initTagPhysics(count) {
  tagPhysics.value = Array.from({ length: count }, (_, i) => {
    const color = tagColors[i % tagColors.length]
    const rotations = [-6, -4, -2, 0, 2, 4, 6]
    const baseRotation = rotations[i % rotations.length] + (Math.random() - 0.5) * 2
    return {
      id: i,
      color,
      baseRotation,
      rotation: baseRotation,
      rotationVelocity: 0,
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      targetX: (Math.random() - 0.5) * 10,
      targetY: (Math.random() - 0.5) * 10,
      springK: 0.015 + Math.random() * 0.01,
      damping: 0.92 + Math.random() * 0.03,
      phase: Math.random() * Math.PI * 2,
      amplitude: 1.5 + Math.random() * 2
    }
  })
}

function getTagStyle(percent, index) {
  const physics = tagPhysics.value[index]
  if (!physics) {
    const color = tagColors[index % tagColors.length]
    return {
      '--size': tagSize(percent),
      '--tag-bg': color.bg,
      '--tag-text': color.text,
      '--tag-border': color.border,
      transform: 'rotate(0deg) translate(0, 0)'
    }
  }
  return {
    '--size': tagSize(percent),
    '--tag-bg': physics.color.bg,
    '--tag-text': physics.color.text,
    '--tag-border': physics.color.border,
    transform: `rotate(${physics.rotation}deg) translate(${physics.x}px, ${physics.y}px)`
  }
}

function getProgress(movie) {
  const progress = movie.progressPercent || (movie.progress?.percent !== undefined ? movie.progress.percent : movie.progress)
  if (typeof progress === 'number') {
    return progress.toFixed(2)
  }
  return '0'
}

const fallbackStats = {
  overview: { total: 128, completionRate: 82 },
  metrics: [
    { key: 'total', label: '片库条目', value: 128, unit: '部', description: '当前片库中的影视条目' },
    { key: 'watched', label: '看过内容', value: 86, unit: '部', description: '已有播放进度的条目' },
    { key: 'watchHours', label: '累计时长', value: 466, unit: '小时', description: '基于播放进度累计' },
    { key: 'favorite', label: '收藏数量', value: 18, unit: '部', description: '已收藏的影视内容' }
  ],
  personality: {
    code: 'CINE',
    title: '光影旅人',
    description: '你更偏爱沉浸式长片、稳定追看和高完成度收藏。',
    confidence: 87,
    traits: ['夜间观影', '科幻偏好', '高完成度', '重看经典'],
    dimensions: [
      { key: 'focus', left: '碎片', right: '聚焦', score: 68, leftScore: 32, rightScore: 68, leftCode: 'S', rightCode: 'F', winner: 'F' },
      { key: 'depth', left: '泛览', right: '深耕', score: 72, leftScore: 28, rightScore: 72, leftCode: 'W', rightCode: 'D', winner: 'D' },
      { key: 'routine', left: '随性', right: '规律', score: 45, leftScore: 55, rightScore: 45, leftCode: 'C', rightCode: 'R', winner: 'C' }
    ],
    scores: { focus: 68, depth: 72, routine: 45 },
    letterScores: { F: 68, S: 32, D: 72, W: 28, R: 45, C: 55 }
  },
  categoryDistribution: [
    { label: '电影', value: 72, percent: 56 },
    { label: '剧集', value: 24, percent: 19 },
    { label: '动漫', value: 19, percent: 15 },
    { label: '纪录', value: 13, percent: 10 }
  ],
  sourceDistribution: [
    { label: 'WebDAV', value: 54, percent: 42 },
    { label: 'OpenList', value: 46, percent: 36 },
    { label: '本地', value: 28, percent: 22 }
  ],
  timeDistribution: Array.from({ length: 24 }, (_, hour) => {
    const curve = hour < 8 ? hour * 2 : hour < 18 ? 20 + (hour - 8) * 5 : 70 + Math.sin(hour) * 20
    return { hour, value: Math.round(curve), percent: Math.max(4, Math.min(100, curve)) }
  }),
  completionStats: [
    { label: '已看完', value: 86, percent: 82 },
    { label: '观看中', value: 24, percent: 18 },
    { label: '未开始', value: 18, percent: 12 }
  ],
  tagDistribution: [
    { label: '科幻', percent: 90 },
    { label: '剧情', percent: 78 },
    { label: '经典', percent: 64 },
    { label: '悬疑', percent: 58 },
    { label: '动画', percent: 46 },
    { label: '公路片', percent: 34 },
    { label: '史诗', percent: 52 },
    { label: '黑色幽默', percent: 28 }
  ],
  recentHistory: []
}

function animateWave() {
  waveTime.value += 0.02
  tagTime.value += 0.016
  
  tagPhysics.value.forEach(physics => {
    const time = tagTime.value
    const sinOffset = Math.sin(time * 1.5 + physics.phase) * physics.amplitude
    
    const springX = (physics.targetX - physics.x) * physics.springK
    const springY = (physics.targetY - physics.y) * physics.springK
    
    physics.vx = (physics.vx + springX + sinOffset * 0.05) * physics.damping
    physics.vy = (physics.vy + springY + sinOffset * 0.03) * physics.damping
    
    const maxSpeed = 1.5
    const speed = Math.sqrt(physics.vx * physics.vx + physics.vy * physics.vy)
    if (speed > maxSpeed) {
      physics.vx = (physics.vx / speed) * maxSpeed
      physics.vy = (physics.vy / speed) * maxSpeed
    }
    
    physics.x += physics.vx
    physics.y += physics.vy
    
    const maxOffset = 25
    physics.x = Math.max(-maxOffset, Math.min(maxOffset, physics.x))
    physics.y = Math.max(-maxOffset, Math.min(maxOffset, physics.y))
    
    physics.rotationVelocity = (physics.rotationVelocity + (physics.baseRotation - physics.rotation) * 0.05) * 0.95
    physics.rotation += physics.rotationVelocity
  })
  
  animationFrameId = requestAnimationFrame(animateWave)
}

onMounted(() => {
  loadStats()
  window.addEventListener('scan:completed', loadStats)
  animateWave()
})

onUnmounted(() => {
  window.removeEventListener('scan:completed', loadStats)
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
  }
})
</script>

<style scoped>
.stats-page {
  min-height: 100%;
  padding: 22px 32px 52px;
  color: var(--mp-text);
  background:
    radial-gradient(circle at 82% 0%, rgba(214, 169, 76, 0.16), transparent 32%),
    radial-gradient(circle at 12% 12%, rgba(70, 213, 197, 0.1), transparent 28%),
    #030506;
}

.stats-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  min-height: 205px;
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(3, 5, 6, 0.9), rgba(3, 5, 6, 0.35), rgba(3, 5, 6, 0.88)),
    url("https://images.unsplash.com/photo-1485846234645-a62644f84728?w=1800&q=85");
  background-position: center;
  background-size: cover;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.34);
}

.kicker {
  color: #5bc4f7;
  font-size: 12px;
  font-weight: 800;
}

h1,
h2,
p {
  margin: 0;
}

.stats-hero h1 {
  margin-top: 8px;
  color: #fff7e8;
  font-size: clamp(36px, 4vw, 56px);
  line-height: 1;
}

.stats-hero p,
.metric-card p,
.panel header span,
.history-item span,
.personality-copy p {
  color: rgba(248, 243, 233, 0.62);
}

.refresh-button {
  height: 40px;
  padding: 0 20px;
  border: 1px solid rgba(102, 126, 234, 0.52);
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(135deg, #667eea, #764ba2);
  font-weight: 800;
  cursor: pointer;
}

.refresh-button:disabled {
  cursor: default;
  opacity: 0.65;
}

.state-card {
  margin-top: 20px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
}

.error-card {
  color: #ff9b8d;
}

.personality-card,
.metric-card,
.panel,
.history-panel {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(10, 13, 14, 0.72);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.26);
  backdrop-filter: blur(16px);
}

.personality-card {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) minmax(280px, 0.9fr);
  gap: 24px;
  align-items: center;
  margin-top: 18px;
  padding: 22px;
}

.personality-code {
  display: grid;
  place-items: center;
  aspect-ratio: 1;
  border: 1px solid rgba(214, 169, 76, 0.28);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(214, 169, 76, 0.2), rgba(70, 213, 197, 0.11));
}

.personality-code strong {
  color: #fff7e8;
  font-size: 40px;
  line-height: 1;
}

.personality-code span {
  margin-top: 8px;
  color: #5bc4f7;
}

.personality-code .confidence {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.insufficient-hint span {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.personality-copy h2,
.panel h2,
.history-panel h2 {
  color: #fff7e8;
  font-size: 20px;
}

.trait-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.trait-list span {
  padding: 6px 10px;
  border-radius: 999px;
  color: #46d5c5;
  background: rgba(70, 213, 197, 0.1);
}

.dimension-list {
  display: grid;
  gap: 16px;
}

.dimension-row {
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.dimension-header {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 10px;
}

.dimension-header strong {
  color: #fff7e8;
  font-size: 14px;
  font-weight: 500;
}

.dimension-winner {
  padding: 2px 6px;
  border-radius: 4px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3));
  color: #5bc4f7;
  font-size: 12px;
  font-weight: 600;
}

.dimension-row-content {
  display: grid;
  grid-template-columns: 70px 1fr 70px;
  gap: 10px;
  align-items: center;
  color: rgba(248, 243, 233, 0.66);
  font-size: 13px;
}

.dimension-label-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.dimension-label-group strong {
  font-size: 10px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dimension-label {
  text-align: center;
}

.dimension-track {
  height: 36px;
  position: relative;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.dimension-track i {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
}

.bar-track {
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
}

.bar-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #667eea, #764ba2);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.metric-card {
  padding: 18px;
}

.metric-card span {
  color: rgba(248, 243, 233, 0.58);
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin: 10px 0 6px;
  color: #fff7e8;
  font-size: 30px;
  line-height: 1;
}

.metric-card small {
  margin-left: 5px;
  color: rgba(248, 243, 233, 0.55);
  font-size: 14px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.panel,
.history-panel {
  padding: 20px;
}

.panel.wide {
  grid-column: span 2;
}

.panel header,
.history-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 17px;
}

.bar-list,
.source-list {
  display: grid;
  gap: 13px;
}

.row-head,
.source-item > div:first-child {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
  color: rgba(248, 243, 233, 0.82);
}

.rhythm-panel {
  overflow: hidden;
}

.clock-chart {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 240px;
  padding: 10px;
}

.clock-container {
  position: relative;
  width: 220px;
  height: 220px;
}

.clock-face {
  position: absolute;
  top: 10px;
  left: 10px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.03);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.08),
    inset 0 0 30px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.clock-sector {
  position: absolute;
  top: 0;
  left: 0;
  width: 200px;
  height: 200px;
  transition: background 0.4s ease, opacity 0.4s ease;
}

.clock-sector.has-data {
  cursor: pointer;
}

.clock-sector.has-data:hover {
  filter: brightness(1.25);
}

.clock-labels {
  position: absolute;
  top: 10px;
  left: 10px;
  width: 200px;
  height: 200px;
  pointer-events: none;
}

.sector-label {
  position: absolute;
  font-size: 10px;
  font-weight: 500;
  transform: translate(-50%, -50%);
  pointer-events: none;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

.clock-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 74px;
  height: 74px;
  border-radius: 50%;
  background: rgba(10, 13, 14, 0.92);
  border: 2px solid rgba(102, 126, 234, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  box-shadow: 0 0 24px rgba(0, 0, 0, 0.45);
}

.center-label {
  color: #5bc4f7;
  font-size: 14px;
  font-weight: 600;
}

.clock-hour-hand {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 2px;
  height: 28px;
  background: linear-gradient(to top, rgba(91, 196, 247, 0.8), transparent);
  transform-origin: center bottom;
  transform: translate(-50%, -100%) rotate(0deg);
  border-radius: 2px;
  z-index: 11;
}

.clock-minute-hand {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 1px;
  height: 34px;
  background: linear-gradient(to top, rgba(91, 196, 247, 0.5), transparent);
  transform-origin: center bottom;
  transform: translate(-50%, -100%) rotate(45deg);
  border-radius: 1px;
  z-index: 11;
}

@keyframes gearRotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.completion-ring {
  display: grid;
  place-items: center;
  width: 138px;
  height: 138px;
  margin: 0 auto 18px;
  border: 12px solid rgba(70, 213, 197, 0.78);
  border-left-color: rgba(214, 169, 76, 0.75);
  border-radius: 50%;
  box-shadow: inset 0 0 30px rgba(0, 0, 0, 0.36);
}

.completion-ring strong {
  color: #fff7e8;
  font-size: 28px;
}

.completion-ring span {
  color: rgba(248, 243, 233, 0.56);
  font-size: 12px;
}

.compact-list {
  gap: 10px;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-content: flex-start;
  min-height: 180px;
  perspective: 1200px;
}

.tag-cloud span {
  position: relative;
  padding: 10px 16px;
  border-radius: 999px;
  color: var(--tag-text);
  font-size: var(--size);
  font-weight: 600;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  cursor: pointer;
  overflow: hidden;
}

.tag-cloud span::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: 
    radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.4), transparent 50%),
    radial-gradient(circle at 70% 70%, rgba(255, 255, 255, 0.15), transparent 40%),
    var(--tag-bg);
  border: 1.5px solid var(--tag-border);
  transition: all 0.3s ease;
}

.tag-cloud span::after {
  content: '';
  position: absolute;
  top: 8%;
  left: 15%;
  width: 25%;
  height: 25%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.2) 70%, transparent);
  filter: blur(2px);
  transition: all 0.3s ease;
}

.tag-cloud span span {
  position: relative;
  z-index: 1;
  padding: 0;
  border: none;
  background: transparent;
  animation: none;
  transform: none;
}

.tag-cloud span:hover {
  transform: scale(1.15) translateY(-8px) !important;
  filter: brightness(1.15) saturate(1.2);
}

.tag-cloud span:hover::before {
  border-width: 2px;
  border-color: rgba(255, 255, 255, 0.8);
  box-shadow: 
    0 0 20px rgba(102, 126, 234, 0.4),
    0 0 40px rgba(118, 75, 162, 0.3),
    0 10px 40px rgba(0, 0, 0, 0.3);
}

.tag-cloud span:hover::after {
  transform: scale(1.3);
  opacity: 1;
}

.history-panel {
  margin-top: 14px;
}

.history-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
}

.history-card {
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  overflow: hidden;
  background-color: #101315;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.history-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 22px 48px rgba(0, 0, 0, 0.38);
}

.history-card .card-image {
  width: 100%;
  height: 210px;
  object-fit: cover;
  object-position: center;
}

.history-card .card-bottom {
  padding: 10px;
}

.history-card strong {
  display: block;
  overflow: hidden;
  color: #fff7e8;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.history-card span {
  display: block;
  margin-top: 4px;
  color: rgba(248, 243, 233, 0.52);
  font-size: 11px;
}

.history-empty {
  grid-column: 1 / -1;
  padding: 24px 0;
  text-align: center;
  color: rgba(248, 243, 233, 0.4);
  font-size: 13px;
}

@media (max-width: 1080px) {
  .personality-card,
  .metric-grid,
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .panel.wide {
    grid-column: auto;
  }
}

@media (max-width: 720px) {
  .stats-page {
    padding: 16px 14px 42px;
  }

  .stats-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .dimension-row {
    grid-template-columns: 44px 1fr 44px;
  }

  .dimension-row strong {
    display: none;
  }
}
</style>
