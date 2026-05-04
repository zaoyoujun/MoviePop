<script setup lang="ts">
import { onMounted } from 'vue'
import { useLibraryStore } from '../stores/library'
import { useAppStore } from '../stores/app'
import MovieGrid from '../components/movie/MovieGrid.vue'

const libraryStore = useLibraryStore()
const appStore = useAppStore()

onMounted(() => {
  libraryStore.loadLibrary('all', 'combined')
})
</script>

<template>
  <div>
    <div v-if="libraryStore.loading" class="loading">加载中...</div>
    <MovieGrid v-else :movies="libraryStore.items" />
  </div>
</template>

<style scoped>
.loading {
  text-align: center;
  padding: 40px;
  color: var(--text-faint);
}
</style>
