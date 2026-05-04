<script setup lang="ts">
import type { Movie } from '../../types/movie'
import { toggleFavorite } from '../../api/movies'
import { useAppStore } from '../../stores/app'

const props = defineProps<{
  movie: Movie
}>()

const appStore = useAppStore()

const emit = defineEmits<{
  click: [movie: Movie]
}>()

function handleClick() {
  emit('click', props.movie)
}

async function handleFavorite(e: Event) {
  e.stopPropagation()
  try {
    const result = await toggleFavorite(props.movie.path)
    appStore.updateStats(result.stats)
    Object.assign(props.movie, result.movie)
  } catch (err) {
    console.error('收藏操作失败', err)
  }
}

const coverUrl = props.movie.cover_url || ''
</script>

<template>
  <div class="movie-card" @click="handleClick">
    <div class="card-cover">
      <img v-if="coverUrl" :src="coverUrl" :alt="movie.title" loading="lazy">
      <div v-else class="cover-placeholder">{{ (movie.title || '?')[0] }}</div>

      <div class="card-badges">
        <span v-if="movie.is_series" class="badge">剧集</span>
        <span v-else class="badge">{{ movie.type }}</span>
      </div>

      <button
        class="favorite-btn"
        :class="{ active: movie.is_favorite }"
        @click="handleFavorite"
        title="收藏"
      >
        {{ movie.is_favorite ? '★' : '☆' }}
      </button>

      <div v-if="movie.playback?.has_progress" class="progress-bar">
        <div class="progress-fill" :style="{ width: movie.playback.percent + '%' }"></div>
      </div>
    </div>

    <div class="card-info">
      <span class="card-title" :title="movie.title">{{ movie.title }}</span>
      <span class="card-meta">
        <span v-if="movie.year">{{ movie.year }}</span>
        <span v-if="movie.source_label" class="source-label">{{ movie.source_label }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.movie-card {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.movie-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
}

.card-cover {
  position: relative;
  aspect-ratio: 2/3;
  overflow: hidden;
  background: var(--panel-muted);
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.movie-card:hover .card-cover img {
  transform: scale(1.05);
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: var(--text-faint);
}

.card-badges {
  position: absolute;
  top: 8px;
  left: 8px;
  display: flex;
  gap: 4px;
}

.badge {
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--text);
}

.favorite-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--text-soft);
  opacity: 0;
  transition: opacity 0.15s;
}

.movie-card:hover .favorite-btn {
  opacity: 1;
}

.favorite-btn.active {
  color: #ffd700;
  opacity: 1;
}

.progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(0, 0, 0, 0.3);
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s;
}

.card-info {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--text-faint);
}

.source-label {
  color: var(--text-faint);
}
</style>
