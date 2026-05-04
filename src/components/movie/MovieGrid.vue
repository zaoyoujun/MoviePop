<script setup lang="ts">
import type { Movie } from '../../types/movie'
import MovieCard from './MovieCard.vue'

defineProps<{
  movies: Movie[]
}>()
</script>

<template>
  <div class="movie-grid">
    <MovieCard v-for="movie in movies" :key="movie.path" :movie="movie" />
    <div v-if="!movies.length" class="empty-state">暂无影片</div>
  </div>
</template>

<style scoped>
.movie-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--card-width), 1fr));
  gap: 18px;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 20px;
  color: var(--text-faint);
  font-size: 15px;
}
</style>
