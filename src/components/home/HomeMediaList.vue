<template>
  <section class="media-section" :class="`mode-${mode}`">
    <header class="section-header">
      <div>
        <h2>{{ title }}</h2>
        <span>{{ subtitle }}</span>
      </div>
      <button v-if="showMore" class="more-button" type="button">
        查看全部
        <n-icon><ChevronForward /></n-icon>
      </button>
    </header>

    <div v-if="cards.length" class="media-rail">
      <div
        v-for="card in cards"
        :key="card.cardKey || card.id"
        class="card-wrapper"
      >
        <article
          class="media-card"
          :ref="(el) => setCardRef(card.cardKey || card.id, el)"
          @click="handleCardClick(card)"
          @mousemove="handleMouseMove($event, card.cardKey || card.id)"
          @mouseleave="handleMouseLeave(card.cardKey || card.id)"
        >
          <img v-if="card.cover" :src="posterFor(card)" :alt="card.title" class="card-image" :style="getImageStyle(card.cardKey || card.id)" />
          <div v-else class="no-poster">
            <n-icon size="32"><ImageOutline /></n-icon>
            <span>{{ card.title?.slice(0, 4) }}</span>
          </div>
          <button v-if="showPlayback" type="button" class="poster-play" title="播放" @click.stop="$emit('play', card.id)">
            <n-icon><Play /></n-icon>
          </button>

          <div v-if="showPlayback" class="progress-line" :title="`播放进度 ${progressFor(card)}%`">
            <i :style="{ width: `${progressFor(card)}%` }"></i>
          </div>
        </article>

        <div class="card-bottom" @click="handleCardClick(card)">
          <strong :title="card.title">{{ card.title }}</strong>
          <p
            v-if="showPlayback && card.continueContext"
            class="continue-context"
            :title="card.continueContext"
          >
            {{ card.continueContext }}
          </p>
          <div class="card-meta">
            <span>{{ card.source }}</span>
            <span v-if="card.year" class="meta-year">{{ formatYear(card.year) }}</span>
          </div>
        </div>
      </div>
    </div>

    <n-empty
      v-if="!loading && !cards.length"
      description="暂无影视条目"
      class="media-empty"
    />
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { ChevronForward, Heart, ImageOutline, Play } from '@vicons/ionicons5'
import { useRouter } from 'vue-router'
import { useDetailTransition } from '@/composables/useDetailTransition'

const router = useRouter()
const { startTransition } = useDetailTransition()

const cardRefs = new Map()

function setCardRef(id, el) {
  if (el) {
    cardRefs.set(id, el)
  }
}

async function handleCardClick(card) {
  const cardKey = card.cardKey || card.id
  const el = cardRefs.get(cardKey)
  if (!el) {
    router.push({ name: 'MovieDetail', params: { id: card.id } })
    return
  }

  const rect = el.getBoundingClientRect()
  const imageSrc = posterFor(card)

  startTransition(imageSrc, rect, card.id)
}

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  cards: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'poster'
  },
  showPlayback: {
    type: Boolean,
    default: false
  },
  showMore: {
    type: Boolean,
    default: true
  }
})

defineEmits(['detail', 'play', 'favorite'])

function posterFor(card) {
  return card.cover || ''
}

function progressFor(card) {
  const value = Number(card.progress ?? card.progressPercent ?? 0)
  if (Number.isFinite(value) && value > 0) return Math.max(0, Math.min(100, value))
  // Continue-watching cards must only show persisted progress.  A generated
  // percentage makes a just-started item look as if it was watched already.
  if (props.showPlayback) return 0
  const seed = String(card.id || card.title || '').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return [0, 19, 28, 42, 58, 68, 76, 87, 100][seed % 9]
}

const imageStyles = ref({})

function handleMouseMove(event, cardId) {
  if (props.mode !== 'poster') return

  const el = cardRefs.get(cardId)
  if (!el) return

  const rect = el.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2

  const rotateY = ((event.clientX - centerX) / (rect.width / 2)) * 8
  const rotateX = -((event.clientY - centerY) / (rect.height / 2)) * 8

  imageStyles.value[cardId] = {
    transform: `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.05)`,
    transition: 'transform 0.1s ease-out'
  }
}

function handleMouseLeave(cardId) {
  if (props.mode !== 'poster') return

  imageStyles.value[cardId] = {
    transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)',
    transition: 'transform 0.3s ease-out'
  }
}

function getImageStyle(cardId) {
  return imageStyles.value[cardId] || {}
}

function formatYear(year) {
  if (!year) return ''
  const value = String(year).trim()
  if (/^\d{4}$/.test(value)) return value

  const match = value.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/)
  if (!match) return value

  const [, parsedYear, month, day] = match
  return `${parsedYear}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}
</script>

<style scoped>
.media-section {
  margin-top: 26px;
}

.section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 13px;
}

.section-header h2 {
  color: #fff7e8;
  font-size: 19px;
  line-height: 1.1;
}

.section-header span {
  display: block;
  margin-top: 6px;
  color: rgba(248, 243, 233, 0.48);
  font-size: 13px;
}

.more-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  border: 0;
  color: rgba(248, 243, 233, 0.64);
  background: transparent;
  cursor: pointer;
}

.more-button:hover {
  color: #5bc4f7;
}

.media-rail {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(178px, 1fr));
  gap: 16px;
}

.mode-wide .media-rail {
  grid-template-columns: repeat(auto-fill, minmax(285px, 1fr));
}

.card-wrapper {
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.28);
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease;
}

.card-wrapper:hover {
  transform: translateY(-7px);
  box-shadow: 0 28px 58px rgba(0, 0, 0, 0.46);
}

.media-card {
  position: relative;
  min-height: 268px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  background-color: #101315;
  cursor: pointer;
  isolation: isolate;
  perspective: 1000px;
}

.card-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  transform-style: preserve-3d;
  transform: perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1);
}

.no-poster {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
  color: rgba(255, 255, 255, 0.4);
}

.no-poster span {
  font-size: 14px;
  font-weight: 500;
}

.mode-wide .media-card {
  min-height: 230px;
}

.media-card:hover {
  border-color: rgba(214, 169, 76, 0.44);
}

.poster-play {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 4;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  color: #667eea;
  background: rgba(255, 255, 255, 0.95);
  cursor: pointer;
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.card-wrapper:hover .poster-play {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1.05);
}

.card-bottom {
  flex: 0 0 auto;
  padding: 12px;
  border: none;
  border-radius: 0;
  background: transparent;
  cursor: pointer;
}

.progress-line {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2;
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.card-wrapper:hover .progress-line {
  opacity: 1;
}

.progress-line i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.45s ease;
}

.card-bottom strong {
  display: block;
  overflow: hidden;
  color: #fff8ea;
  font-size: 16px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.continue-context {
  margin: 6px 0 0;
  overflow: hidden;
  color: rgba(143, 202, 255, 0.86);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: 0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.card-meta span {
  color: rgba(248, 243, 233, 0.52);
  font-size: 12px;
}

.card-meta .meta-year {
  color: rgba(248, 243, 233, 0.42);
}

.media-empty {
  padding: 42px 0;
}

@media (max-width: 720px) {
  .media-rail,
  .mode-wide .media-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .media-card,
  .mode-wide .media-card {
    min-height: 240px;
  }
}
</style>
