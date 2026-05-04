import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchBootstrap } from '../api/bootstrap'
import type { AppConfig, MovieStats, JobStatus } from '../types/config'

export const useAppStore = defineStore('app', () => {
  const config = ref<AppConfig | null>(null)
  const stats = ref<MovieStats>({ all: 0, remote: 0, local: 0, favorite: 0, recent: 0 })
  const theme = ref<string>('amber')
  const hasLibrary = ref(false)
  const loading = ref(true)
  const activeJob = ref<JobStatus | null>(null)

  const availableThemes = computed(() => config.value?.available_themes || ['amber', 'graphite', 'forest', 'coast'])

  async function bootstrap() {
    loading.value = true
    try {
      const data = await fetchBootstrap()
      config.value = data.config
      stats.value = data.stats
      hasLibrary.value = data.has_library
      theme.value = data.config.interface_theme || data.config.ui_theme || 'amber'
      applyTheme(theme.value)
    } finally {
      loading.value = false
    }
  }

  function loadTheme() {
    const saved = localStorage.getItem('jimihua-theme') || 'amber'
    theme.value = saved
    applyTheme(saved)
    bootstrap()
  }

  function setTheme(newTheme: string) {
    theme.value = newTheme
    localStorage.setItem('jimihua-theme', newTheme)
    applyTheme(newTheme)
  }

  function applyTheme(t: string) {
    document.documentElement.setAttribute('data-theme', t)
  }

  function updateStats(newStats: MovieStats) {
    stats.value = newStats
  }

  return {
    config,
    stats,
    theme,
    hasLibrary,
    loading,
    activeJob,
    availableThemes,
    bootstrap,
    loadTheme,
    setTheme,
    updateStats,
  }
})
