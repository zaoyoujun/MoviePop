<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { useLibraryStore } from '../../stores/library'
import { refreshLibrary } from '../../api/library'
import { useJobPolling } from '../../composables/useJobPolling'

const route = useRoute()
const appStore = useAppStore()
const libraryStore = useLibraryStore()
const { startPolling } = useJobPolling()

const searchInput = ref('')

const viewMeta: Record<string, { kicker: string; title: string; subtitle: string }> = {
  '/': { kicker: '媒体库', title: '我的片库', subtitle: '集中浏览本地与 WebDAV 的影视内容。' },
  '/recommend': { kicker: '推荐', title: '为你推荐', subtitle: '根据收藏、播放进度、标签和评分生成个性化推荐。' },
  '/favorites': { kicker: '收藏', title: '我的收藏', subtitle: '保留你想长期留着的影片和剧集。' },
  '/recent': { kicker: '最近播放', title: '最近播放', subtitle: '回到最近看过的内容，接着播放。' },
  '/local': { kicker: '本地视频', title: '本地视频', subtitle: '浏览本地目录中的视频文件。' },
  '/report': { kicker: '报告', title: '观影报告', subtitle: '基于你的收藏、播放和评分生成可视化观影分析。' },
  '/settings': { kicker: '设置', title: '应用设置', subtitle: '管理片库来源、播放器和扫描目录。' },
}

const currentMeta = computed(() => viewMeta[route.path] || viewMeta['/'])

watch(searchInput, (val) => {
  libraryStore.setSearch(val)
})

async function handleRefresh() {
  try {
    const data = await refreshLibrary('combined')
    appStore.activeJob = { ...data, name: 'refresh-combined-library', status: 'running', current: 0, total: 0, message: '正在刷新...', error: '', result: null }
    startPolling(data.job_id)
  } catch (e) {
    console.error('刷新失败', e)
  }
}
</script>

<template>
  <header class="topbar">
    <div class="headline">
      <span class="headline-kicker">{{ currentMeta.kicker }}</span>
      <h2>{{ currentMeta.title }}</h2>
      <p>{{ currentMeta.subtitle }}</p>
    </div>
    <div class="toolbar">
      <label class="search-field">
        <span>搜索</span>
        <input v-model="searchInput" type="search" placeholder="按标题、别名、简介筛选">
      </label>
      <button class="toolbar-btn accent" @click="handleRefresh">刷新片库</button>
    </div>
  </header>
</template>

<script lang="ts">
import { computed } from 'vue'
</script>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  flex-wrap: wrap;
}

.headline-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--accent);
  font-weight: 600;
}

.headline h2 {
  font-size: 24px;
  margin: 4px 0;
  color: var(--text);
}

.headline p {
  font-size: 13px;
  color: var(--text-faint);
  margin: 0;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-soft);
}

.search-field input {
  width: 240px;
  padding: 8px 12px;
  font-size: 13px;
}

.toolbar-btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s;
}

.toolbar-btn.accent {
  background: var(--accent);
  color: #fff;
}

.toolbar-btn.accent:hover {
  background: var(--accent-strong);
}
</style>
