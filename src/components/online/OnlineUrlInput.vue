<template>
  <div class="online-url-input">
    <div class="input-row">
      <div class="url-input-wrapper">
        <n-icon><Link /></n-icon>
        <input
          v-model.trim="url"
          type="text"
          placeholder="粘贴视频网站URL（支持 Bilibili、YouTube、抖音等）"
          @keyup.enter="handleExtract"
        />
      </div>
      <n-button
        type="primary"
        :loading="extracting"
        :disabled="!url || extracting"
        @click="handleExtract"
      >
        <template #icon>
          <n-icon><DownloadOutline /></n-icon>
        </template>
        解析
      </n-button>
    </div>

    <div v-if="extractError" class="error-message">
      <n-icon color="#ff6b6b"><AlertCircle /></n-icon>
      {{ extractError }}
    </div>

    <div v-if="extractedVideos.length" class="extracted-results">
      <h4>解析结果</h4>
      <div class="video-list">
        <div v-for="video in extractedVideos" :key="video.id" class="video-item">
          <div class="video-cover">
            <img v-if="video.coverUrl" :src="video.coverUrl" :alt="video.title" />
            <div v-else class="no-cover">
              <n-icon size="24"><ImageOutline /></n-icon>
            </div>
          </div>
          <div class="video-info">
            <strong>{{ video.title }}</strong>
            <div class="video-meta">
              <span v-if="video.durationText">{{ video.durationText }}</span>
              <span v-if="video.year">{{ video.year }}</span>
              <span v-if="video.uploader">{{ video.uploader }}</span>
            </div>
          </div>
          <n-button
            size="small"
            type="primary"
            :loading="addingId === video.id"
            @click="handleAddVideo(video)"
          >
            添加到库
          </n-button>
        </div>
      </div>
    </div>

    <div v-if="showSuccess" class="success-message">
      <n-icon color="#67c23a"><CheckmarkCircleOutline /></n-icon>
      视频已成功添加到影视库！
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Link, DownloadOutline, AlertCircle, ImageOutline, CheckmarkCircleOutline } from '@vicons/ionicons5'
import { extractOnlineVideo, addOnlineVideo } from '@/api/movie'

const emit = defineEmits(['added'])

const url = ref('')
const extracting = ref(false)
const extractedVideos = ref([])
const extractError = ref('')
const addingId = ref('')
const showSuccess = ref(false)

async function handleExtract() {
  if (!url.value.trim()) return
  
  extracting.value = true
  extractError.value = ''
  extractedVideos.value = []
  
  try {
    const data = await extractOnlineVideo(url.value.trim())
    if (data.videos && data.videos.length) {
      extractedVideos.value = data.videos
    } else {
      extractError.value = '未解析到视频信息，请检查URL是否正确'
    }
  } catch (error) {
    extractError.value = error.message || '解析失败，请重试'
  } finally {
    extracting.value = false
  }
}

async function handleAddVideo(video) {
  addingId.value = video.id
  
  try {
    await addOnlineVideo(video)
    showSuccess.value = true
    extractedVideos.value = extractedVideos.value.filter(v => v.id !== video.id)
    emit('added')
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)
  } catch (error) {
    extractError.value = error.message || '添加失败'
  } finally {
    addingId.value = ''
  }
}
</script>

<style scoped>
.online-url-input {
  padding: 16px;
  border-radius: 12px;
  background: rgba(10, 13, 14, 0.85);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.input-row {
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

.extracted-results {
  margin-top: 16px;
}

.extracted-results h4 {
  color: #fff7e8;
  font-size: 15px;
  margin-bottom: 12px;
}

.video-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.video-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.video-cover {
  width: 80px;
  height: 45px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.05);
}

.video-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-cover {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.3);
}

.video-info {
  flex: 1;
  min-width: 0;
}

.video-info strong {
  display: block;
  color: #fff7e8;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.video-meta span {
  color: rgba(248, 243, 233, 0.45);
  font-size: 12px;
}

.success-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #67c23a;
  background: rgba(103, 194, 58, 0.1);
  font-size: 13px;
}

@media (max-width: 760px) {
  .input-row {
    flex-direction: column;
  }
  
  .url-input-wrapper {
    width: 100%;
  }
}
</style>