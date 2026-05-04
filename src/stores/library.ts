import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchLibrary } from '../api/library'
import type { Movie, MovieStats } from '../types/movie'

export const useLibraryStore = defineStore('library', () => {
  const items = ref<Movie[]>([])
  const loading = ref(false)
  const searchQuery = ref('')

  async function loadLibrary(mode = 'all', source = 'remote', forceRefresh = false) {
    loading.value = true
    try {
      const data = await fetchLibrary({ mode, source, search: searchQuery.value, force_refresh: forceRefresh })
      items.value = data.items
      return data.stats
    } finally {
      loading.value = false
    }
  }

  function setSearch(query: string) {
    searchQuery.value = query
  }

  return { items, loading, searchQuery, loadLibrary, setSearch }
})
