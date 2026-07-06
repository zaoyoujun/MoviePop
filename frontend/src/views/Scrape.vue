<template>
  <Teleport to="body">
    <div v-if="visible" class="scrape-modal-overlay" @click.self="handleClose">
      <div class="scrape-modal">
        <!-- 弹窗头部 -->
        <div class="scrape-modal-header">
          <div class="header-left">
            <n-icon size="20"><SearchOutline /></n-icon>
            <h2 class="modal-title">影视资源极速刮削</h2>
          </div>
          <n-button ghost size="small" class="close-btn" @click="handleClose">
            <n-icon><Close /></n-icon>
          </n-button>
        </div>

        <!-- Tab 切换 -->
        <div class="scrape-modal-tabs">
          <n-tabs v-model:value="activeTab" type="line" animated>
            <n-tab-pane name="scrape" tab="在线刮削">
              <div class="scrape-tab-content">
                <div class="scrape-wrap">
                  <!-- 左侧搜索结果区 -->
                  <div class="left-search">
                    <div class="form-card">
                      <!-- 搜索框 -->
                      <div class="scrape-source-box">
                        <n-select
                          v-model:value="scrapeSource"
                          :options="sourceOptions"
                          class="source-select"
                        />
                        <n-input
                          v-model:value="searchKeyword"
                          placeholder="输入影视/番剧名称搜索..."
                          class="search-input"
                          @keyup.enter="handleSearch"
                        />
                        <n-button
                          type="primary"
                          class="search-btn"
                          :loading="isSearching"
                          @click="handleSearch"
                        >
                          搜索
                        </n-button>
                        <n-button ghost class="clear-btn" @click="clearForm">清空</n-button>
                      </div>

                      <!-- 搜索结果列表 -->
                      <div v-if="searchResults.length > 0" class="search-results">
                        <article
                          v-for="(result, index) in searchResults"
                          :key="index"
                          class="result-item"
                        >
                          <div class="result-visual">
                            <img class="result-poster" :src="result.poster" alt="海报">
                            <img v-if="result.backdrop" class="result-backdrop" :src="result.backdrop" alt="横版">
                          </div>
                          <div class="result-info">
                            <div class="result-title">
                              {{ result.title }}
                              <n-tag v-if="result.year" class="year-tag">{{ result.year }}</n-tag>
                              <n-tag class="source-tag" :class="result.source">{{ result.sourceLabel }}</n-tag>
                            </div>
                            <div class="result-meta">
                              <span v-if="result.genres?.length">{{ result.genres.join(' / ') }}</span>
                              <span v-if="result.countries?.length">· {{ result.countries.join(' / ') }}</span>
                            </div>
                            <div class="result-desc">{{ result.description }}</div>
                          </div>
                          <div class="result-actions">
                            <n-button size="small" type="primary" @click="submitScrape(result, 'all')">应用全部</n-button>
                            <n-button size="small" @click="submitScrape(result, 'metadata')">仅元数据</n-button>
                            <n-button size="small" @click="submitScrape(result, 'poster')">仅封面</n-button>
                            <n-button size="small" :disabled="!result.backdrop" @click="submitScrape(result, 'backdrop')">仅横版图</n-button>
                          </div>
                        </article>
                      </div>

                      <!-- 无结果提示 -->
                      <div v-if="showNoResult" class="no-result">
                        <n-icon size="48"><SearchOutline /></n-icon>
                        <p>未找到相关结果，请尝试其他关键词</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </n-tab-pane>

            <n-tab-pane name="custom" tab="自定义资料">
              <div class="custom-tab-content">
                <div class="form-card">
                  <div class="card-title">
                    <n-icon><PencilOutline /></n-icon>
                    完全自定义资料
                  </div>

                  <div class="custom-form">
                    <div class="form-row">
                      <div class="form-item">
                        <n-form-item label="标题">
                          <n-input v-model:value="customForm.title" placeholder="输入标题" />
                        </n-form-item>
                        <n-form-item label="原始标题">
                          <n-input v-model:value="customForm.originalTitle" placeholder="输入原始标题" />
                        </n-form-item>
                      </div>

                      <div class="form-row">
                        <n-form-item label="年份">
                          <n-input v-model:value="customForm.year" type="number" placeholder="输入年份" />
                        </n-form-item>
                        <n-form-item label="评分">
                          <n-input v-model:value="customForm.score" type="number" placeholder="0-10" />
                        </n-form-item>
                        <n-form-item label="片长">
                          <n-input v-model:value="customForm.duration" placeholder="例如：120分钟" />
                        </n-form-item>
                      </div>

                      <div class="form-row">
                        <n-form-item label="类型/标签">
                          <n-input v-model:value="customForm.tagsInput" placeholder="多个标签用逗号分隔" />
                        </n-form-item>
                        <n-form-item label="国家/地区">
                          <n-input v-model:value="customForm.countriesInput" placeholder="多个国家用逗号分隔" />
                        </n-form-item>
                        <n-form-item label="语言">
                          <n-input v-model:value="customForm.languagesInput" placeholder="例如：中文" />
                        </n-form-item>
                      </div>

                      <div class="form-row">
                        <n-form-item label="简介">
                          <n-input v-model:value="customForm.description" type="textarea" :rows="3" placeholder="输入简介" />
                        </n-form-item>
                      </div>

                      <div class="form-row">
                        <n-form-item label="竖版封面 URL">
                          <n-input v-model:value="customForm.coverUrl" placeholder="输入封面图片URL" />
                        </n-form-item>
                        <n-form-item label="横版图 URL">
                          <n-input v-model:value="customForm.backdropUrl" placeholder="输入横版图片URL" />
                        </n-form-item>
                      </div>

                      <div class="form-row">
                        <n-form-item label="锁定资料">
                          <div class="lock-toggle">
                            <n-switch v-model:value="customForm.metadataLocked" @update:value="handleLockChange" />
                            <span class="lock-tip">锁定后自动扫描和自动刮削不会覆盖这些资料</span>
                          </div>
                        </n-form-item>
                      </div>

                      <div class="form-preview">
                        <div v-if="customForm.coverUrl" class="preview-image poster-preview-small">
                          <img :src="customForm.coverUrl" alt="封面预览">
                        </div>
                        <div v-if="customForm.backdropUrl" class="preview-image backdrop-preview-small">
                          <img :src="customForm.backdropUrl" alt="横版预览">
                        </div>
                      </div>

                      <div class="form-actions">
                        <n-button ghost @click="resetCustomForm">重置</n-button>
                        <n-button type="primary" :loading="isSubmittingCustom" @click="submitCustom">保存自定义资料</n-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { SearchOutline, Close, PencilOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { apiUrl } from '@/api/request'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  movieId: {
    type: String,
    default: ''
  },
  metadataLocked: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'success'])

const activeTab = ref('scrape')
const scrapeSource = ref('')
const searchKeyword = ref('')
const searchResults = ref([])
const isSearching = ref(false)
const showNoResult = ref(false)
const isSubmittingCustom = ref(false)

const sourceOptions = ref([
  { label: 'Auto (自动)', value: 'auto' },
  { label: 'TMDB (全球影视)', value: 'tmdb' },
  { label: 'AniBK (动漫番剧)', value: 'anibk' },
  { label: 'Douban (豆瓣)', value: 'douban' }
])

const customForm = reactive({
  title: '',
  originalTitle: '',
  year: '',
  description: '',
  score: '',
  tagsInput: '',
  genres: [],
  countriesInput: '',
  countries: [],
  languagesInput: '',
  languages: [],
  duration: '',
  coverUrl: '',
  backdropUrl: '',
  metadataLocked: false
})

async function loadScrapeSources() {
  try {
    const response = await fetch(apiUrl('/scrape/sources'), {
      method: 'GET'
    })
    const data = await response.json()
    if (data.code === 0 && data.data && Array.isArray(data.data)) {
      sourceOptions.value = data.data.map(item => ({
        label: item.label || item.name || item.value,
        value: item.value || item.key || item.source
      }))
      if (sourceOptions.value.length > 0) {
        scrapeSource.value = sourceOptions.value[0].value
      }
    }
  } catch (error) {
    scrapeSource.value = 'auto'
  }
}

function handleClose() {
  emit('close')
}

async function handleSearch() {
  const keyword = searchKeyword.value.trim()
  if (!keyword || !scrapeSource.value) return

  isSearching.value = true
  showNoResult.value = false

  try {
    const response = await fetch(apiUrl('/scrape/search'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: scrapeSource.value, keyword: keyword })
    })
    const data = await response.json()

    if (data.code === 0 && data.data && Array.isArray(data.data)) {
      searchResults.value = data.data.map(item => ({
        title: item.title || item.name || '',
        year: item.year || '',
        description: item.description || item.overview || '',
        poster: item.posterUrl || item.coverUrl || item.poster || '',
        backdrop: item.backdropUrl || '',
        source: (item.source || scrapeSource.value).toLowerCase(),
        sourceLabel: getSourceLabel(item.source || scrapeSource.value),
        genres: item.genres || [],
        countries: item.countries || item.country ? [item.country] : [],
        raw: item
      }))
      showNoResult.value = searchResults.value.length === 0
    } else {
      searchResults.value = []
      showNoResult.value = true
    }
  } catch (error) {
    searchResults.value = []
    showNoResult.value = true
  } finally {
    isSearching.value = false
  }
}

function getSourceLabel(source) {
  const labelMap = { tmdb: 'TMDB', anibk: 'AniBK', douban: 'Douban', auto: 'Auto' }
  return labelMap[source?.toLowerCase()] || source?.toUpperCase() || 'Unknown'
}

function clearForm() {
  searchKeyword.value = ''
  searchResults.value = []
  showNoResult.value = false
}

async function submitScrape(result, applyMode) {
  try {
    let data = {}
    switch (applyMode) {
      case 'all':
        data = {
          title: result.title,
          source: result.source,
          year: result.year,
          description: result.description,
          coverUrl: result.poster,
          backdropUrl: result.backdrop,
          genres: result.genres,
          countries: result.countries
        }
        break
      case 'metadata':
        data = {
          title: result.title,
          year: result.year,
          description: result.description,
          genres: result.genres,
          countries: result.countries,
          duration: ''
        }
        break
      case 'poster':
        data = { coverUrl: result.poster }
        break
      case 'backdrop':
        data = { backdropUrl: result.backdrop }
        break
    }

    const response = await fetch(apiUrl('/scrape/submit'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        movieId: props.movieId || '',
        applyMode,
        data
      })
    })
    const res = await response.json()
    if (res.code === 0) {
      emit('success')
      handleClose()
    } else {
      alert(res.message || '应用失败')
    }
  } catch (error) {
    alert('应用失败：' + error.message)
  }
}

async function submitCustom() {
  const formData = {
    title: customForm.title,
    originalTitle: customForm.originalTitle,
    year: customForm.year ? parseInt(customForm.year) : null,
    description: customForm.description,
    score: customForm.score ? parseFloat(customForm.score) : null,
    tags: customForm.tagsInput.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    genres: customForm.tagsInput.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    countries: customForm.countriesInput.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    languages: customForm.languagesInput.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    duration: customForm.duration,
    coverUrl: customForm.coverUrl,
    backdropUrl: customForm.backdropUrl,
    metadataLocked: customForm.metadataLocked
  }

  isSubmittingCustom.value = true
  try {
    const response = await fetch(
      apiUrl(`/movies/${props.movieId}/metadata/custom`),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      }
    )
    const res = await response.json()
    if (res.code === 0) {
      emit('success')
      handleClose()
    } else {
      alert(res.message || '保存失败')
    }
  } catch (error) {
    alert('保存失败：' + error.message)
  } finally {
    isSubmittingCustom.value = false
  }
}

async function handleLockChange(locked) {
  try {
    const response = await fetch(
      apiUrl(`/movies/${props.movieId}/metadata/lock`),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ locked })
      }
    )
    const res = await response.json()
    if (res.code !== 0) {
      customForm.metadataLocked = !locked
      alert(res.message || '锁定操作失败')
    }
  } catch (error) {
    customForm.metadataLocked = !locked
    alert('锁定操作失败：' + error.message)
  }
}

function resetCustomForm() {
  customForm.title = ''
  customForm.originalTitle = ''
  customForm.year = ''
  customForm.description = ''
  customForm.score = ''
  customForm.tagsInput = ''
  customForm.countriesInput = ''
  customForm.languagesInput = ''
  customForm.duration = ''
  customForm.coverUrl = ''
  customForm.backdropUrl = ''
  customForm.metadataLocked = props.metadataLocked || false
}

watch(() => props.visible, (val) => {
  if (val) {
    activeTab.value = 'scrape'
    loadScrapeSources()
    clearForm()
    customForm.metadataLocked = props.metadataLocked || false
  }
})

watch(() => props.metadataLocked, (val) => {
  customForm.metadataLocked = val
})

onMounted(() => {
  if (props.visible) {
    loadScrapeSources()
    customForm.metadataLocked = props.metadataLocked || false
  }
})
</script>

<style scoped>
.scrape-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.scrape-modal {
  width: 90%;
  max-width: 1100px;
  max-height: 85vh;
  background: #0d1117;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  overflow: hidden;
  animation: slideUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  display: flex;
  flex-direction: column;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.scrape-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.modal-title {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.close-btn {
  color: #a0a0b0;
}

.close-btn:hover {
  color: #ffffff;
}

.scrape-modal-tabs {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.scrape-tab-content,
.custom-tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.scrape-wrap {
  display: flex;
  flex-direction: column;
}

.form-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  padding: 24px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 16px;
}

.card-title::before {
  content: '';
  width: 4px;
  height: 16px;
  background: #6366f1;
  border-radius: 2px;
}

.scrape-source-box {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.source-select {
  flex: 0 0 140px;
}

.search-input {
  flex: 1;
  min-width: 200px;
}

.search-btn {
  flex: 0 0 90px;
}

.clear-btn {
  flex: 0 0 70px;
}

.search-results {
  margin-top: 16px;
  max-height: 500px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  margin-bottom: 12px;
  border: 1px solid transparent;
  transition: all 0.25s ease;
}

.result-item:hover {
  border-color: #6366f1;
}

.result-visual {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.result-poster {
  width: 90px;
  height: 130px;
  border-radius: 6px;
  object-fit: cover;
  background: #1a1a2e;
}

.result-backdrop {
  width: 90px;
  height: 50px;
  border-radius: 6px;
  object-fit: cover;
  background: #1a1a2e;
}

.result-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.result-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.year-tag {
  font-size: 12px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.source-tag {
  font-size: 11px;
  padding: 2px 6px;
}

.source-tag.tmdb { color: #01b4e4; background: rgba(1, 180, 228, 0.1); }
.source-tag.anibk { color: #f472b6; background: rgba(244, 114, 182, 0.1); }
.source-tag.douban { color: #00bf63; background: rgba(0, 191, 99, 0.1); }
.source-tag.auto { color: #fbbf24; background: rgba(251, 191, 36, 0.1); }

.result-meta {
  font-size: 13px;
  color: #a0a0b0;
  margin-bottom: 8px;
}

.result-desc {
  font-size: 13px;
  color: #a0a0b0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
  padding-top: 8px;
}

.result-actions .n-button {
  min-width: 80px;
}

.no-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #a0a0b0;
}

.no-result p {
  margin-top: 12px;
}

.custom-form {
  max-height: 500px;
  overflow-y: auto;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item {
  flex: 1;
}

.lock-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lock-tip {
  font-size: 13px;
  color: #a0a0b0;
}

.form-preview {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.preview-image {
  border-radius: 8px;
  overflow: hidden;
  background: #1a1a2e;
}

.poster-preview-small {
  width: 100px;
  height: 145px;
}

.backdrop-preview-small {
  width: 200px;
  height: 110px;
}

.preview-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

@media (max-width: 768px) {
  .scrape-modal {
    width: 95%;
    max-height: 90vh;
  }

  .result-item {
    flex-direction: column;
  }

  .result-visual {
    flex-direction: row;
  }

  .result-backdrop {
    width: auto;
    flex: 1;
  }

  .result-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .result-actions .n-button {
    flex: 1;
    min-width: auto;
  }

  .scrape-source-box {
    flex-direction: column;
  }

  .source-select, .search-input, .search-btn, .clear-btn {
    flex: 1;
    min-width: 100%;
  }

  .form-preview {
    flex-direction: column;
  }

  .backdrop-preview-small {
    width: 100%;
    height: 150px;
  }
}
</style>
