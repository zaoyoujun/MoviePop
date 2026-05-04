<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchRecommendations } from '../api/recommendations'
import type { RecommendationDashboard } from '../types/recommendation'

const dashboard = ref<RecommendationDashboard | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    dashboard.value = await fetchRecommendations()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="recommend-view">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="dashboard" class="recommend-content">
      <div v-if="dashboard.items.length" class="section">
        <h3>猜你喜欢</h3>
        <div class="recommend-grid">
          <div v-for="item in dashboard.items" :key="item.movie.path" class="recommend-card">
            <div class="card-cover">
              <img v-if="item.movie.cover_url" :src="item.movie.cover_url" :alt="item.movie.title" loading="lazy">
              <div v-else class="cover-placeholder">{{ item.movie.title[0] }}</div>
            </div>
            <div class="card-info">
              <span class="card-title">{{ item.movie.title }}</span>
              <span class="card-score">推荐度 {{ Math.round(item.score * 100) }}%</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="dashboard.external_items.length" class="section">
        <h3>外部推荐</h3>
        <div class="recommend-grid">
          <div v-for="(item, i) in dashboard.external_items" :key="i" class="recommend-card">
            <div class="card-cover">
              <img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy">
              <div v-else class="cover-placeholder">{{ item.title[0] }}</div>
            </div>
            <div class="card-info">
              <span class="card-title">{{ item.title }}</span>
              <span class="card-source">{{ item.source }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading { text-align: center; padding: 40px; color: var(--text-faint); }
.recommend-content { display: flex; flex-direction: column; gap: 24px; }
.section h3 { margin: 0 0 16px; font-size: 16px; color: var(--text); }
.recommend-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
.recommend-card {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: transform 0.15s;
}
.recommend-card:hover { transform: translateY(-2px); }
.card-cover { aspect-ratio: 2/3; overflow: hidden; background: var(--panel-muted); }
.card-cover img { width: 100%; height: 100%; object-fit: cover; }
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: var(--text-faint);
}
.card-info { padding: 10px; display: flex; flex-direction: column; gap: 2px; }
.card-title { font-size: 13px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-score { font-size: 11px; color: var(--accent); }
.card-source { font-size: 11px; color: var(--text-faint); text-transform: uppercase; }
</style>
