<template>
  <div class="online-page">
    <div class="page-header">
      <div class="header-left">
        <n-button
          type="primary"
          size="small"
          @click="goBack"
        >
          <n-icon><ArrowBackOutline /></n-icon>
          返回首页
        </n-button>
      </div>

      <div class="url-input-wrapper">
        <n-icon><Link /></n-icon>
        <input
          v-model.trim="url"
          type="text"
          placeholder="粘贴视频网站URL"
          @keyup.enter="handleBrowse"
        />
        <n-button
          type="primary"
          size="small"
          :loading="loading"
          @click="handleBrowse"
        >
          <n-icon><Globe /></n-icon>
        </n-button>
      </div>

      <div class="header-right">
        <n-button
          size="small"
          :disabled="!currentUrl"
          @click="refreshPage"
        >
          <n-icon><RefreshOutline /></n-icon>
        </n-button>
      </div>
    </div>

    <div v-if="currentUrl" class="browser-toolbar">
      <div class="nav-buttons">
        <n-button
          size="small"
          :disabled="historyIndex <= 0"
          @click="goBackHistory"
        >
          <n-icon><ArrowBackOutline /></n-icon>
        </n-button>
        <n-button
          size="small"
          :disabled="historyIndex >= history.length - 1"
          @click="goForward"
        >
          <n-icon><ArrowForwardOutline /></n-icon>
        </n-button>
      </div>

      <div class="current-url">
        <n-icon><Globe /></n-icon>
        <span>{{ currentUrl }}</span>
      </div>

      <div class="action-buttons">
        <n-button
          size="small"
          type="primary"
          :loading="extracting"
          :disabled="!currentUrl"
          @click="handleExtractVideo"
        >
          <template #icon>
            <n-icon><PlayCircleOutline /></n-icon>
          </template>
          用应用播放
        </n-button>
      </div>
    </div>

    <div v-if="error" class="error-message">
      <n-icon color="#ff6b6b"><AlertCircle /></n-icon>
      {{ error }}
    </div>

    <div v-if="currentUrl" class="iframe-container">
      <iframe
        ref="iframeRef"
        :src="currentUrl"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        @load="handleIframeLoad"
      ></iframe>
    </div>

    <div v-else class="empty-state">
      <n-icon size="64"><Globe /></n-icon>
      <h2>在线浏览</h2>
      <p>输入视频网站URL，在应用内浏览网站内容</p>
      <p class="hint">点击视频链接会自动使用应用播放器播放</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Link, Globe, AlertCircle, ArrowBackOutline, ArrowForwardOutline,
  RefreshOutline, PlayCircleOutline
} from '@vicons/ionicons5'
import { browseOnlineSite } from '@/api/movie'
import { startPlay } from '@/composables/usePlayer'

const router = useRouter()
const route = useRoute()

const iframeRef = ref(null)
const url = ref('')
const loading = ref(false)
const extracting = ref(false)
const error = ref('')
const currentUrl = ref('')
const history = ref([])
const historyIndex = ref(-1)

let videoClickHandler = null

onMounted(() => {
  const initialUrl = route.query.url
  if (initialUrl) {
    url.value = initialUrl
    handleBrowse()
  }

  window.addEventListener('online:play-video', handleVideoPlayEvent)

  if (window.electronAPI && window.electronAPI.onVideoClick) {
    videoClickHandler = window.electronAPI.onVideoClick((data) => {
      if (data && data.url) {
        handleExtractAndPlay(data.url)
      }
    })
  }
})

onUnmounted(() => {
  window.removeEventListener('online:play-video', handleVideoPlayEvent)
  if (videoClickHandler) {
    videoClickHandler()
  }
})

function goBack() {
  router.push('/home')
}

async function handleBrowse() {
  if (!url.value.trim()) return

  loading.value = true
  error.value = ''

  try {
    let targetUrl = url.value.trim()
    if (!targetUrl.startsWith('http')) {
      targetUrl = 'https://' + targetUrl
    }

    currentUrl.value = targetUrl
    history.value = [targetUrl]
    historyIndex.value = 0
  } catch (err) {
    error.value = err.message || '打开网站失败'
  } finally {
    loading.value = false
  }
}

function goBackHistory() {
  if (historyIndex.value > 0) {
    historyIndex.value--
    currentUrl.value = history.value[historyIndex.value]
  }
}

function goForward() {
  if (historyIndex.value < history.value.length - 1) {
    historyIndex.value++
    currentUrl.value = history.value[historyIndex.value]
  }
}

function refreshPage() {
  if (iframeRef.value) {
    iframeRef.value.contentWindow.location.reload()
  }
}

function handleIframeLoad() {
  if (iframeRef.value) {
    const newUrl = iframeRef.value.contentWindow.location.href
    if (newUrl !== currentUrl.value) {
      history.value = history.value.slice(0, historyIndex.value + 1)
      history.value.push(newUrl)
      historyIndex.value++
      currentUrl.value = newUrl
    }

    injectVideoInterceptor()
  }
}

function injectVideoInterceptor() {
  try {
    const iframeDoc = iframeRef.value?.contentDocument || iframeRef.value?.contentWindow?.document
    if (!iframeDoc) return

    const script = iframeDoc.createElement('script')
    script.textContent = `
      document.addEventListener('click', function(e) {
        var target = e.target;
        while (target) {
          if (target.tagName === 'A' && target.href) {
            var href = target.href;
            if (href.includes('/v/') || href.includes('/p/') || href.includes('/video/') || href.includes('.mp4') || href.includes('.m3u8')) {
              e.preventDefault();
              e.stopPropagation();
              window.postMessage({ type: 'MOVIEPOP_VIDEO_CLICK', url: href }, '*');
              return;
            }
          }
          target = target.parentNode;
        }
      }, true);
    `
    iframeDoc.head.appendChild(script)

    window.addEventListener('message', handleIframeMessage)
  } catch (e) {
    console.warn('Failed to inject video interceptor:', e)
  }
}

function handleIframeMessage(event) {
  if (event.data && event.data.type === 'MOVIEPOP_VIDEO_CLICK') {
    const videoUrl = event.data.url
    handleExtractAndPlay(videoUrl)
  }
}

function handleVideoPlayEvent(event) {
  const videoInfo = event.detail
  if (videoInfo) {
    startPlay(videoInfo)
  }
}

async function handleExtractVideo() {
  if (!currentUrl.value) return
  await handleExtractAndPlay(currentUrl.value)
}

async function handleExtractAndPlay(videoUrl) {
  extracting.value = true
  error.value = ''

  try {
    const data = await browseOnlineSite(videoUrl)
    
    if (data.videos && data.videos.length > 0) {
      const video = data.videos[0]
      
      await startPlay({
        movieId: video.id,
        movieTitle: video.title,
        episodeId: '',
        episodeTitle: '',
        cover: video.coverUrl || video.thumbnail || '',
        episodeList: data.videos.length > 1 ? data.videos.slice(1) : [],
        seasonIndex: 0
      })
    } else {
      error.value = '未找到视频内容，请先打开视频播放页面'
    }
  } catch (err) {
    error.value = err.message || '提取视频失败'
  } finally {
    extracting.value = false
  }
}
</script>

<style scoped>
.online-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0a0d0e;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(20, 24, 26, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-left {
  flex-shrink: 0;
}

.url-input-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.58);
  background: rgba(10, 13, 14, 0.7);
}

.url-input-wrapper input {
  flex: 1;
  border: 0;
  outline: none;
  color: #fff7e8;
  background: transparent;
}

.url-input-wrapper input::placeholder {
  color: rgba(248, 243, 233, 0.42);
}

.header-right {
  flex-shrink: 0;
}

.browser-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.nav-buttons {
  display: flex;
  gap: 4px;
}

.current-url {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  color: rgba(248, 243, 233, 0.55);
  font-size: 12px;
  overflow: hidden;
}

.current-url span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 16px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #ff6b6b;
  background: rgba(255, 107, 107, 0.1);
  font-size: 13px;
}

.iframe-container {
  flex: 1;
  background: #000;
}

.iframe-container iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(248, 243, 233, 0.45);
}

.empty-state h2 {
  color: #fff7e8;
  font-size: 24px;
  margin: 20px 0 10px 0;
}

.empty-state p {
  margin: 5px 0;
  font-size: 14px;
}

.empty-state .hint {
  font-size: 12px;
  color: rgba(248, 243, 233, 0.3);
  margin-top: 15px;
}

@media (max-width: 760px) {
  .page-header {
    flex-wrap: wrap;
  }

  .url-input-wrapper {
    width: 100%;
    order: 3;
  }
}
</style>