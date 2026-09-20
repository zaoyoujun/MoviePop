<template>
  <div class="first-boot">
    <div class="boot-card">
      <div class="brand-mark">M</div>
      <h1>欢迎使用 MoviePop</h1>
      <p class="subtitle">正在下载精选影视数据库（约 1 万条），完成后即可浏览热门榜单与个性化推荐。</p>

      <!-- 下载进度 -->
      <div v-if="phase === 'downloading'" class="progress-block">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
        <div class="progress-meta">
          <span>{{ statusLabel }}</span>
          <span>{{ progressPct }}%</span>
        </div>
        <p v-if="lastError" class="error-text">{{ lastError }}</p>
      </div>

      <!-- 下载完成 -->
      <div v-else-if="phase === 'done'" class="done-block">
        <div class="done-mark">✓</div>
        <p>数据准备完成，正在进入应用…</p>
      </div>

      <!-- 连接后端失败 -->
      <div v-else-if="phase === 'error'" class="error-block">
        <p>无法连接后端服务，请确认媒体服务已启动。</p>
        <button type="button" class="retry-btn" @click="init">重试</button>
      </div>

      <div class="skip-row">
        <button type="button" class="skip-btn" @click="skip">
          {{ skipLabel }}
        </button>
        <button
          v-if="phase === 'downloading'"
          type="button"
          class="cancel-btn"
          :disabled="cancelling"
          @click="cancelDownload"
        >
          {{ cancelling ? '取消中…' : '取消下载并进入' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api/request'
import { getJobsStatus, refreshAll, cancelJob } from '@/api/jobs'

const router = useRouter()
const phase = ref('idle')        // idle / downloading / done / error
const progressPct = ref(0)
const statusLabel = ref('等待开始…')
const lastError = ref('')
const cancelling = ref(false)
let pollTimer = null

const skipLabel = computed(() => {
  if (phase.value === 'downloading') return '跳过，下载将在后台继续'
  if (phase.value === 'error') return '稍后手动下载，进入应用'
  return '进入应用'
})

async function init() {
  phase.value = 'downloading'
  lastError.value = ''
  progressPct.value = 0
  statusLabel.value = '正在检查本地数据…'

  // 本地已有精选数据库 → 直接进入应用，绝不触发全量下载
  try {
    const poolData = await get('/pool/count')
    const count = Number(poolData?.count ?? 0)
    if (count > 0) {
      phase.value = 'done'
      statusLabel.value = `本地已有 ${count} 条精选数据`
      setTimeout(() => router.replace('/home'), 300)
      return
    }
  } catch {
    // 后端未就绪时不阻塞：允许直接进入应用，用户可在设置页稍后手动下载
    phase.value = 'done'
    setTimeout(() => router.replace('/home'), 300)
    return
  }

  // 仅当本地无精选数据时，才触发全量下载
  statusLabel.value = '正在启动下载任务…'
  try {
    await refreshAll()
    startPolling()
  } catch (err) {
    phase.value = 'error'
    lastError.value = err?.message || '触发下载失败'
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(pollOnce, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollOnce() {
  try {
    const data = await getJobsStatus()
    // 后端返回所有任务的状态，取首次下载任务（pool_initial）
    const task = data?.pool_initial || {}
    const pct = Math.min(100, Math.max(0, Math.round((task.progress ?? 0) * 100)))
    progressPct.value = pct
    statusLabel.value = task.label || task.status || '下载中…'

    if (task.error === 'cancelled') {
      stopPolling()
      router.replace('/home')
      return
    }
    if (task.done || pct >= 100) {
      stopPolling()
      phase.value = 'done'
      setTimeout(() => router.replace('/home'), 800)
    }
  } catch (err) {
    // 轮询失败不立即退出，保留上次进度
    lastError.value = err?.message || '查询进度失败'
  }
}

function skip() {
  // 跳过前端等待；后端任务（若在跑）会继续在后台完成，稍后在设置页可看进度
  stopPolling()
  router.replace('/home')
}

async function cancelDownload() {
  if (phase.value !== 'downloading' || cancelling.value) return
  cancelling.value = true
  stopPolling()
  statusLabel.value = '正在取消下载…'
  try {
    await cancelJob('pool_initial')
  } catch {
    // 取消接口失败不阻塞进入
  } finally {
    cancelling.value = false
    router.replace('/home')
  }
}

onMounted(init)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.first-boot {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at 72% -18%, rgba(214, 169, 76, 0.13), transparent 34%),
    radial-gradient(circle at 16% 8%, rgba(70, 213, 197, 0.1), transparent 30%),
    #030506;
}

.boot-card {
  width: 100%;
  max-width: 460px;
  padding: 40px 36px 32px;
  text-align: center;
  background: linear-gradient(180deg, rgba(11, 17, 19, 0.96), rgba(5, 8, 10, 0.98));
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  margin: 0 auto 20px;
  border-radius: 12px;
  color: #fff;
  font-weight: 900;
  font-size: 22px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  box-shadow: 0 0 30px rgba(102, 126, 234, 0.3);
}

.boot-card h1 {
  margin: 0 0 8px;
  color: #fff5dc;
  font-size: 24px;
}

.subtitle {
  margin: 0 0 28px;
  color: rgba(248, 243, 233, 0.6);
  font-size: 14px;
  line-height: 1.6;
}

.progress-block {
  text-align: left;
}

.progress-bar {
  width: 100%;
  height: 8px;
  margin-bottom: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 999px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #46d5c5);
  border-radius: 999px;
  transition: width 0.4s ease;
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  color: rgba(248, 243, 233, 0.7);
  font-size: 13px;
}

.error-text {
  margin: 10px 0 0;
  color: #e85a5a;
  font-size: 12px;
}

.done-block {
  padding: 12px 0 4px;
}

.done-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  border-radius: 50%;
  color: #46d5c5;
  font-size: 22px;
  background: rgba(70, 213, 197, 0.15);
}

.done-block p {
  color: rgba(248, 243, 233, 0.7);
  font-size: 14px;
}

.error-block p {
  margin: 0 0 16px;
  color: #e85a5a;
  font-size: 14px;
}

.retry-btn {
  padding: 8px 24px;
  color: #fff5dc;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.retry-btn:hover {
  background: rgba(255, 255, 255, 0.14);
}

.skip-row {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 32px;
}

.skip-btn {
  background: none;
  border: none;
  color: rgba(248, 243, 233, 0.4);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.2s ease;
}

.skip-btn:hover {
  color: rgba(248, 243, 233, 0.7);
}

.cancel-btn {
  padding: 7px 18px;
  color: rgba(232, 90, 90, 0.85);
  font-size: 13px;
  background: rgba(232, 90, 90, 0.08);
  border: 1px solid rgba(232, 90, 90, 0.3);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.cancel-btn:hover:not(:disabled) {
  background: rgba(232, 90, 90, 0.16);
  border-color: rgba(232, 90, 90, 0.55);
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}
</style>
