<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { useTheme } from '../../composables/useTheme'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const { theme, setTheme } = useTheme()

const navItems = [
  { path: '/', label: '我的片库', view: 'all' },
  { path: '/recommend', label: '推荐', view: 'recommend' },
  { path: '/favorites', label: '收藏', view: 'favorite' },
  { path: '/recent', label: '最近播放', view: 'recent' },
  { path: '/local', label: '本地视频', view: 'local' },
  { path: '/report', label: '观影报告', view: 'report' },
  { path: '/settings', label: '设置', view: 'settings' },
]

function navigate(path: string) {
  router.push(path)
}

function cycleTheme() {
  const themes = appStore.availableThemes
  const idx = themes.indexOf(theme)
  const next = themes[(idx + 1) % themes.length]
  setTheme(next)
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand-block">
      <span class="brand-kicker">家庭影视库</span>
      <h1>鸡米花</h1>
      <p>合并本地与 WebDAV 的家庭影视库</p>
    </div>

    <nav class="nav-list">
      <button
        v-for="item in navItems"
        :key="item.path"
        class="nav-item"
        :class="{ active: route.path === item.path }"
        @click="navigate(item.path)"
      >
        {{ item.label }}
      </button>
    </nav>

    <div class="sidebar-footer">
      <button class="theme-btn" @click="cycleTheme" :title="`当前主题: ${theme}`">
        {{ theme }}
      </button>
      <div class="sidebar-status">
        <span class="status-dot" :class="{ connected: appStore.hasLibrary }"></span>
        <span>{{ appStore.hasLibrary ? '已连接' : '未配置' }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  min-height: 100vh;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 24px 18px;
  flex-shrink: 0;
}

.brand-block {
  margin-bottom: 28px;
}

.brand-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: var(--accent);
  font-weight: 600;
}

.brand-block h1 {
  font-size: 22px;
  margin: 6px 0 4px;
  color: var(--text);
}

.brand-block p {
  font-size: 12px;
  color: var(--text-faint);
  margin: 0;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.nav-item {
  background: transparent;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-soft);
  text-align: left;
  transition: all 0.15s;
}

.nav-item:hover {
  background: var(--panel-muted);
  color: var(--text);
}

.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: auto;
}

.theme-btn {
  background: var(--panel-muted);
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-soft);
  text-transform: capitalize;
}

.sidebar-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-faint);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger);
}

.status-dot.connected {
  background: var(--success);
}
</style>
