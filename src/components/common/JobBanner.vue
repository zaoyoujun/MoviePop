<script setup lang="ts">
import { useAppStore } from '../../stores/app'

const appStore = useAppStore()
</script>

<template>
  <section v-if="appStore.activeJob" class="job-banner">
    <div>
      <strong>后台任务进行中</strong>
      <p>{{ appStore.activeJob.message || '请稍候' }}</p>
    </div>
    <div class="job-progress">
      <span>{{ appStore.activeJob.current }} / {{ appStore.activeJob.total }}</span>
      <div class="progress-track">
        <span
          class="progress-bar"
          :style="{ width: appStore.activeJob.total > 0 ? (appStore.activeJob.current / appStore.activeJob.total * 100) + '%' : '0%' }"
        ></span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.job-banner {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.job-banner strong {
  font-size: 14px;
  color: var(--text);
}

.job-banner p {
  font-size: 12px;
  color: var(--text-soft);
  margin: 2px 0 0;
}

.job-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-faint);
}

.progress-track {
  width: 120px;
  height: 4px;
  background: var(--panel-muted);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.3s;
}
</style>
