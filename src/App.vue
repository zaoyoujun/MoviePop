<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from './stores/app'
import AppShell from './components/layout/AppShell.vue'

const appStore = useAppStore()

onMounted(() => {
  appStore.loadTheme()
})
</script>

<template>
  <AppShell />
</template>
