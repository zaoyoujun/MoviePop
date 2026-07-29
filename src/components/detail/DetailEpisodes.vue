<template>
  <section v-if="shouldShowSection" class="episode-section">
    <div class="episode-header">
      <h2 class="section-title">
        <n-icon><TvOutline /></n-icon>
        {{ sectionTitle }}
      </h2>
      <span>{{ currentEpisodes.length }} 集</span>
    </div>

    <!-- 一级：季；二级：当前季内的篇章或版本，始终分行呈现。 -->
    <div v-if="seasons.length > 1" class="selector-row primary-selector-row">
      <div class="season-selector compact">
        <button
          v-for="season in seasons"
          :key="season.seasonNumber"
          class="season-btn"
          :class="{ active: currentSeasonNumber === season.seasonNumber }"
          type="button"
          @click="selectSeason(season.seasonNumber)"
        >
          {{ season.name }}
        </button>
      </div>
    </div>

    <div v-if="visibleChapters.length > 1" class="selector-row secondary-selector-row">
      <span class="selector-label">{{ chapterSelectorLabel }}</span>
      <div class="season-selector compact">
        <button
          v-for="chapter in visibleChapters"
          :key="chapter.index"
          class="season-btn"
          :class="{ active: currentVersion === chapter.index }"
          type="button"
          @click="selectVersion(chapter.index)"
        >
          {{ chapterOptionLabel(chapter.item) }}
        </button>
      </div>
    </div>

    <div class="episode-carousel">
      <button class="rail-arrow left" type="button" title="上一组" @click="scrollEpisodes(-1)">
        <n-icon><ChevronBack /></n-icon>
      </button>

      <div ref="railRef" class="episode-rail">
        <article
          v-for="episode in currentEpisodes"
          :key="episode.id"
          class="episode-card"
          :class="{ watched: episode.progress >= 90, playing: isPlaying }"
          :title="`双击播放：${episode.title}`"
          @dblclick="handleDoubleClick(episode)"
        >
          <div class="episode-thumb">
            <img :src="thumbnailFor(episode)" :alt="episode.title" loading="lazy" />
            <div v-if="episode.progress > 0 && episode.progress < 90" class="episode-progress">
              <div class="progress-fill" :style="{ width: `${episode.progress}%` }"></div>
            </div>
            <div v-if="episode.progress >= 90" class="watched-badge">
              <n-icon><CheckmarkOutline /></n-icon>
            </div>
          </div>
          <strong class="episode-title">{{ episode.title }}</strong>
        </article>
      </div>

      <button class="rail-arrow right" type="button" title="下一组" @click="scrollEpisodes(1)">
        <n-icon><ChevronForward /></n-icon>
      </button>
    </div>

    <p v-if="showHint" class="play-hint">双击剧集开始播放...</p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { CheckmarkOutline, ChevronBack, ChevronForward, TvOutline } from '@vicons/ionicons5'

const props = defineProps({
  versions: {
    type: Array,
    default: () => []
  },
  mediaVersions: {
    type: Array,
    default: () => []
  },
  seasons: {
    type: Array,
    default: () => []
  },
  modelValue: {
    type: Number,
    default: 0
  },
  fallbackImage: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'play'])

const railRef = ref(null)
const isPlaying = ref(false)
const showHint = ref(false)
const currentSeasonNumber = ref(props.seasons[0]?.seasonNumber || 1)

const currentVersion = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const currentSeason = computed(() => {
  return props.seasons.find(s => s.seasonNumber === currentSeasonNumber.value) || props.seasons[0] || null
})

const currentEpisodes = computed(() => {
  if (props.versions[currentVersion.value]) {
    return props.versions[currentVersion.value].episodes || []
  }
  if (currentSeason.value) {
    return currentSeason.value.episodes || []
  }
  return []
})

const visibleChapters = computed(() => {
  let filtered = props.versions

  // 季导航项是聚合对象；按季号关联独立的版本/篇章条目。
  if (props.seasons.length > 1) {
    filtered = filtered.filter(v => Number(v.seasonNumber || 1) === Number(currentSeasonNumber.value))
  }

  return filtered.map((item) => ({
    item,
    index: props.versions.indexOf(item)
  }))
})

const chapterSelectorLabel = computed(() => {
  return visibleChapters.value.some(({ item }) => item.part) ? '篇章 / 版本' : '版本'
})

const totalEpisodes = computed(() => {
  return props.versions.reduce((sum, v) => sum + (v.episodes?.length || 0), 0)
})

const shouldShowSection = computed(() => {
  if (props.seasons.length > 1) return true
  if (props.mediaVersions.length > 1) return true
  if (visibleChapters.value.length > 1) return true
  return totalEpisodes.value > 1
})

const sectionTitle = computed(() => {
  if (props.seasons.length > 1 || props.mediaVersions.length > 1 || visibleChapters.value.length > 1) {
    return '剧集'
  }
  return '选集'
})

function selectSeason(seasonNumber) {
  currentSeasonNumber.value = seasonNumber
  let index = props.versions.findIndex(v => Number(v.seasonNumber || 1) === Number(seasonNumber))
  if (index >= 0) {
    currentVersion.value = index
  }
}

function selectVersion(index) {
  currentVersion.value = index
}

function chapterOptionLabel(item) {
  const part = Number(item.part || 0)
  const chapterName = String(item.chapterName || '').trim()
  const versionTitle = String(item.versionTitle || '').trim()

  if (part) {
    const label = `第 ${part} 篇`
    return versionTitle && versionTitle !== chapterName ? `${label} · ${versionTitle}` : label
  }
  return versionTitle || chapterName || item.name || '默认版本'
}

function thumbnailFor(episode) {
  const current = props.versions[currentVersion.value] || currentSeason.value || {}
  return episode.thumbnailUrl ||
    episode.stillUrl ||
    episode.imageUrl ||
    episode.coverUrl ||
    episode.backdropUrl ||
    current.backdropUrl ||
    current.coverUrl ||
    props.fallbackImage ||
    'https://images.unsplash.com/photo-1485846234645-a62644f84728?w=640&q=80'
}

function scrollEpisodes(direction) {
  const rail = railRef.value
  if (!rail) return
  rail.scrollBy({
    left: direction * Math.max(rail.clientWidth * 0.74, 360),
    behavior: 'smooth'
  })
}

function handleDoubleClick(episode) {
  if (isPlaying.value) return
  isPlaying.value = true
  emit('play', {
    version: currentVersion.value,
    episode: episode.episodeNumber,
    title: episode.title,
    versionName: props.versions[currentVersion.value]?.name
  })
  setTimeout(() => {
    isPlaying.value = false
  }, 3000)
}
</script>

<style scoped>
.episode-section {
  margin-bottom: 48px;
}

.episode-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 28px;
  margin-bottom: 38px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.episode-header > span {
  color: rgba(255, 255, 255, 0.56);
  font-size: 21px;
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  margin: 0;
  color: #fff;
  font-size: 34px;
  font-weight: 800;
}

.season-selector,
.version-block {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 18px;
}

.selector-row {
  display: flex;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 28px;
}

.primary-selector-row {
  display: block;
}

.secondary-selector-row {
  padding-top: 10px;
}

.selector-label {
  flex: 0 0 132px;
  padding-top: 15px;
  color: rgba(255, 255, 255, 0.68);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.08em;
  white-space: nowrap;
}

.version-block {
  gap: 12px;
}

.season-selector.compact {
  flex: 1;
  margin-bottom: 0;
}

.switch-label {
  color: rgba(255, 255, 255, 0.54);
  font-size: 13px;
  font-weight: 700;
}

.season-btn {
  min-height: 62px;
  padding: 0 36px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 18px;
  color: rgba(255, 255, 255, 0.76);
  background: rgba(255, 255, 255, 0.055);
  cursor: pointer;
}

.season-btn:hover,
.season-btn.active {
  border-color: rgba(255, 255, 255, 0.34);
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
}

.episode-carousel {
  position: relative;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 40px;
  gap: 12px;
  align-items: center;
}

.episode-rail {
  display: grid;
  grid-auto-columns: clamp(220px, 18.5vw, 268px);
  grid-auto-flow: column;
  gap: 12px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 2px 20px;
  scroll-behavior: smooth;
  scroll-snap-type: x proximity;
  scrollbar-color: rgba(255, 255, 255, 0.42) rgba(255, 255, 255, 0.08);
  scrollbar-width: thin;
}

.episode-rail::-webkit-scrollbar {
  height: 6px;
}

.episode-rail::-webkit-scrollbar-track {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.episode-rail::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.46);
}

.rail-arrow {
  display: grid;
  place-items: center;
  width: 34px;
  height: 74px;
  border: 0;
  color: rgba(255, 255, 255, 0.88);
  background: transparent;
  cursor: pointer;
  font-size: 34px;
}

.rail-arrow:hover {
  color: #fff;
  transform: scale(1.08);
}

.episode-card {
  min-width: 0;
  scroll-snap-align: start;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.episode-card:hover {
  transform: translateY(-3px);
}

.episode-card.playing {
  opacity: 0.62;
  pointer-events: none;
}

.episode-thumb {
  position: relative;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.26);
}

.episode-thumb::after {
  position: absolute;
  inset: 0;
  content: "";
  background: linear-gradient(180deg, transparent 54%, rgba(0, 0, 0, 0.28));
  opacity: 0;
  transition: opacity 0.2s ease;
}

.episode-card:hover .episode-thumb::after {
  opacity: 1;
}

.episode-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.episode-title {
  display: block;
  overflow: hidden;
  margin-top: 8px;
  color: #fff;
  font-size: 24px;
  font-weight: 600;
  font-weight: 800;
  line-height: 1.25;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.episode-progress {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 2;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: rgba(255, 255, 255, 0.86);
}

.watched-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 3;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: #071016;
  background: rgba(255, 255, 255, 0.88);
}

.play-hint {
  margin-top: 12px;
  color: rgba(255, 255, 255, 0.56);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 768px) {
  .selector-row {
    display: block;
    margin-bottom: 20px;
  }

  .selector-label {
    display: block;
    padding-top: 0;
    margin-bottom: 12px;
  }

  .season-btn {
    min-height: 46px;
    padding: 0 20px;
    border-radius: 13px;
    font-size: 17px;
  }

  .episode-carousel {
    grid-template-columns: 28px minmax(0, 1fr) 28px;
    gap: 6px;
  }

  .episode-rail {
    grid-auto-columns: minmax(190px, 72vw);
  }

  .rail-arrow {
    width: 28px;
    font-size: 28px;
  }
}
</style>
