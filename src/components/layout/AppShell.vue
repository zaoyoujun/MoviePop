<script setup lang="ts">
import { useAppStore } from '../../stores/app'
import Sidebar from './Sidebar.vue'
import TopBar from './TopBar.vue'
import JobBanner from '../common/JobBanner.vue'
import Toast from '../common/Toast.vue'
import FirstRunWizard from '../modals/FirstRunWizard.vue'

const appStore = useAppStore()
</script>

<template>
  <div class="app-shell">
    <Sidebar />
    <main class="main-shell">
      <TopBar />
      <JobBanner v-if="appStore.activeJob" />
      <router-view />
    </main>
  </div>
  <FirstRunWizard v-if="!appStore.loading && !appStore.hasLibrary" />
  <Toast />
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
}

.main-shell {
  flex: 1;
  min-width: 0;
  padding: var(--main-padding);
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
