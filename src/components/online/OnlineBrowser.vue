<template>
  <div class="online-browser">
    <div class="browser-header">
      <div class="url-input-row">
        <div class="url-input-wrapper">
          <n-icon><Link /></n-icon>
          <input
            v-model.trim="url"
            type="text"
            placeholder="粘贴视频网站URL（如 Bilibili、YouTube等）"
            @keyup.enter="handleOpen"
          />
        </div>
        <n-button
          type="primary"
          :loading="loading"
          :disabled="!url || loading"
          @click="handleOpen"
        >
          <template #icon>
            <n-icon><Globe /></n-icon>
          </template>
          打开网站
        </n-button>
      </div>

      <div v-if="error" class="error-message">
        <n-icon color="#ff6b6b"><AlertCircle /></n-icon>
        {{ error }}
      </div>
    </div>

    <div class="browser-info">
      <div class="info-item">
        <n-icon><LinkOutline /></n-icon>
        <span>点击"打开网站"在独立页面中浏览</span>
      </div>
      <div class="info-item">
        <n-icon><PlayCircleOutline /></n-icon>
        <span>浏览时点击"用应用播放"使用应用播放器</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Link, Globe, AlertCircle, LinkOutline, PlayCircleOutline } from '@vicons/ionicons5'

const router = useRouter()
const url = ref('')
const loading = ref(false)
const error = ref('')

async function handleOpen() {
  if (!url.value.trim()) return

  loading.value = true
  error.value = ''

  try {
    let targetUrl = url.value.trim()
    if (!targetUrl.startsWith('http')) {
      targetUrl = 'https://' + targetUrl
    }
    router.push({ path: '/online', query: { url: targetUrl } })
  } catch (err) {
    error.value = err.message || '打开网站失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.online-browser {
  padding: 16px;
  border-radius: 12px;
  background: rgba(10, 13, 14, 0.85);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.browser-header {
  margin-bottom: 16px;
}

.url-input-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.url-input-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.58);
  background: rgba(10, 13, 14, 0.7);
}

.url-input-wrapper input {
  width: 100%;
  border: 0;
  outline: none;
  color: #fff7e8;
  background: transparent;
}

.url-input-wrapper input::placeholder {
  color: rgba(248, 243, 233, 0.42);
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #ff6b6b;
  background: rgba(255, 107, 107, 0.1);
  font-size: 13px;
}

.browser-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(248, 243, 233, 0.45);
  font-size: 13px;
}

@media (max-width: 760px) {
  .url-input-row {
    flex-direction: column;
  }

  .url-input-wrapper {
    width: 100%;
  }
}
</style>