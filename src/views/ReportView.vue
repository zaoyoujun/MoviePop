<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchReport } from '../api/report'
import type { ReportData } from '../types/report'

const report = ref<ReportData | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    report.value = await fetchReport()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="report-view">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="report" class="report-content">
      <div class="overview-cards">
        <div class="overview-card">
          <span class="card-value">{{ report.overview.total_movies }}</span>
          <span class="card-label">总影片</span>
        </div>
        <div class="overview-card">
          <span class="card-value">{{ report.overview.favorites }}</span>
          <span class="card-label">收藏</span>
        </div>
        <div class="overview-card">
          <span class="card-value">{{ report.overview.total_watch_hours }}h</span>
          <span class="card-label">观影时长</span>
        </div>
        <div class="overview-card">
          <span class="card-value">{{ report.overview.avg_rating }}</span>
          <span class="card-label">平均评分</span>
        </div>
      </div>

      <div class="chart-section">
        <h3>类型分布</h3>
        <div class="bar-chart">
          <div v-for="item in report.type_distribution" :key="item.name" class="bar-item">
            <span class="bar-label">{{ item.name }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: item.percent + '%' }"></div>
            </div>
            <span class="bar-value">{{ item.count }}</span>
          </div>
        </div>
      </div>

      <div class="chart-section">
        <h3>完播统计</h3>
        <div class="completion-stats">
          <span>已看完: {{ report.completion_stats.completed }}</span>
          <span>观看中: {{ report.completion_stats.in_progress }}</span>
          <span>未开始: {{ report.completion_stats.not_started }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading { text-align: center; padding: 40px; color: var(--text-faint); }
.report-content { display: flex; flex-direction: column; gap: 24px; }
.overview-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }
.overview-card {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.card-value { font-size: 28px; font-weight: 700; color: var(--accent); }
.card-label { font-size: 13px; color: var(--text-faint); }
.chart-section { background: var(--panel-strong); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 20px; }
.chart-section h3 { margin: 0 0 16px; font-size: 16px; color: var(--text); }
.bar-chart { display: flex; flex-direction: column; gap: 10px; }
.bar-item { display: flex; align-items: center; gap: 12px; }
.bar-label { width: 80px; font-size: 13px; color: var(--text-soft); text-align: right; }
.bar-track { flex: 1; height: 8px; background: var(--panel-muted); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.5s; }
.bar-value { width: 40px; font-size: 13px; color: var(--text-faint); }
.completion-stats { display: flex; gap: 24px; font-size: 14px; color: var(--text-soft); }
</style>
