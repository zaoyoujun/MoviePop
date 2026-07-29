/**
 * 设置页面
 *
 * 功能模块：
 * 1. 主题设置 - 暗色模式开关
 * 2. 通知设置 - 通知开关
 * 3. 语言设置 - 语言选择下拉框
 * 4. 内置服务器 - 启用开关、端口设置、启动/停止控制
 *
 * 使用组件：
 * - n-h2: 标题组件
 * - n-form: 表单组件
 * - n-form-item: 表单项组件
 * - n-switch: 开关组件
 * - n-select: 选择组件
 * - n-button: 按钮组件
 */
<template>
  <div class="settings-page">
    <!-- ==================== 页面标题 ==================== -->
    <n-h2>设置</n-h2>

    <!-- ==================== 设置表单 ==================== -->
    <n-form label-placement="left" label-width="120">
      <!-- 主题设置 -->
      <n-form-item label="主题">
        <n-switch v-model:value="darkMode" />
        <span class="switch-label">暗色模式</span>
      </n-form-item>

      <!-- 通知设置 -->
      <n-form-item label="通知">
        <n-switch v-model:value="notification" />
        <span class="switch-label">开启通知</span>
      </n-form-item>

      <!-- 语言设置 -->
      <n-form-item label="语言">
        <n-select
          v-model:value="language"
          :options="langOptions"
          class="lang-select"
        />
      </n-form-item>

      <!-- 内置服务器设置 -->
      <div class="server-section">
        <n-h3>内置服务器</n-h3>
        <n-form-item label="启用">
          <n-switch v-model:value="serverEnabled" @update:value="onServerEnabledChange" />
          <span class="switch-label">开启内置服务器</span>
        </n-form-item>
        
        <template v-if="serverEnabled">
          <n-form-item label="端口号">
            <n-input
              v-model:value="serverPort"
              type="number"
              class="port-input"
              :disabled="serverRunning"
            />
            <span class="port-tip">默认端口：8080</span>
          </n-form-item>
          
          <n-form-item label="服务器状态">
            <div class="status-indicator">
              <span 
                class="status-dot" 
                :class="{ running: serverRunning, stopped: !serverRunning }"
              ></span>
              <span class="status-text">{{ serverRunning ? '运行中' : '已停止' }}</span>
              <span v-if="serverRunning" class="server-url">
                http://localhost:{{ serverPort }}
              </span>
            </div>
          </n-form-item>
          
          <n-form-item label="用户名">
            <div class="credential-display">
              <n-input
                v-model:value="serverUsername"
                class="credential-input"
                readonly
              />
            </div>
          </n-form-item>
          
          <n-form-item label="密码">
            <div class="credential-display">
              <n-input
                v-model:value="serverPassword"
                class="credential-input"
                :type="showPassword ? 'text' : 'password'"
                readonly
              />
              <n-button
                v-if="serverPassword"
                ghost
                size="small"
                @click="showPassword = !showPassword"
              >
                {{ showPassword ? '隐藏' : '显示' }}
              </n-button>
              <n-button
                v-if="serverPassword"
                ghost
                size="small"
                @click="copyPassword"
              >
                复制
              </n-button>
            </div>
          </n-form-item>
          
          <n-form-item label="操作">
            <div class="server-actions">
              <n-button
                v-if="!serverRunning"
                type="primary"
                @click="startServer"
                :disabled="isStarting"
              >
                {{ isStarting ? '启动中...' : '启动服务器' }}
              </n-button>
              <n-button
                v-else
                type="error"
                @click="stopServer"
                :disabled="isStopping"
              >
                {{ isStopping ? '停止中...' : '停止服务器' }}
              </n-button>
              <n-button
                v-if="serverRunning"
                ghost
                @click="openServerUrl"
              >
                打开地址
              </n-button>
              <n-button
                type="info"
                @click="toggleAutoStart"
                :disabled="isProcessing"
              >
                {{ autoStart ? '取消自动启动' : '自动启动' }}
              </n-button>
              <n-button
                ghost
                @click="downloadServer"
                :disabled="isDownloading"
              >
                {{ isDownloading ? '下载中...' : '下载/更新' }}
              </n-button>
              <n-button
                ghost
                type="warning"
                @click="uninstallServer"
                :disabled="isProcessing"
              >
                卸载
              </n-button>
            </div>
          </n-form-item>
        </template>
      </div>

      <!-- 刮削设置 -->
      <div class="scraper-section">
        <n-h3>刮削设置</n-h3>
        <n-form-item label="豆瓣Cookie">
          <n-input
            v-model:value="doubanCookie"
            type="textarea"
            rows="3"
            class="cookie-input"
            placeholder="请输入豆瓣Cookie"
          />
          <div class="input-tip">用于获取影片信息和评分</div>
        </n-form-item>
        
        <n-form-item label="TMDB API密钥">
          <div class="api-key-row">
            <n-input
              v-model:value="tmdbApiKey"
              class="api-key-input"
              placeholder="请输入TMDB API密钥"
            />
            <a 
              href="https://www.themoviedb.org/" 
              target="_blank" 
              class="tmdb-link"
            >
              申请API密钥
            </a>
          </div>
          <div class="input-tip">用于获取影片海报、简介等信息</div>
        </n-form-item>
        
        <n-form-item label="操作">
          <n-button type="primary" @click="saveScraperSettings">
            保存设置
          </n-button>
        </n-form-item>
      </div>

      <!-- 播放器设置 -->
      <div class="player-section">
        <n-h3>播放器</n-h3>
        <p class="player-description">
          AI 超分使用内置的 Anime4K 与 FSRCNNX 实时 GPU Shader；仅在片源需要放大时生效。
        </p>

        <n-form-item label="硬件解码">
          <n-select
            v-model:value="playerSettings.hwdec"
            :options="playerHwdecOptions"
            class="player-select"
          />
          <div class="input-tip">此项会在下次打开播放器时生效。</div>
        </n-form-item>

        <n-form-item label="默认画质增强">
          <n-select
            v-model:value="playerSettings.enhancement_profile"
            :options="playerEnhancementOptions"
            class="player-select"
          />
          <div class="input-tip">Anime4K 适合动漫；FSRCNNX 适合通用影片。AI 超分不会对不需要放大的 4K 片源重复处理。</div>
        </n-form-item>

        <n-form-item label="默认补帧">
          <n-select
            v-model:value="playerSettings.frame_profile"
            :options="playerFrameOptions"
            class="player-select"
          />
          <div class="input-tip">“显示插帧”会按显示器刷新率平滑展示；左上角会显示如 24 → 165 FPS。</div>
        </n-form-item>

        <n-form-item label="字幕">
          <n-select
            v-model:value="playerSettings.subtitle_mode"
            :options="playerSubtitleOptions"
            class="player-select"
          />
        </n-form-item>

        <n-form-item label="默认音量">
          <div class="player-volume-row">
            <n-slider v-model:value="playerSettings.volume" :min="0" :max="100" :step="1" class="player-volume-slider" />
            <span class="player-volume-value">{{ playerSettings.volume }}%</span>
          </div>
        </n-form-item>

        <n-form-item label="播放信息">
          <n-switch v-model:value="playerSettings.show_playback_info" />
          <span class="switch-label">鼠标移入时显示画质与帧率</span>
        </n-form-item>

        <n-form-item label="窗口置顶">
          <n-switch v-model:value="playerSettings.always_on_top" />
          <span class="switch-label">新打开的播放器默认置顶</span>
        </n-form-item>

        <n-form-item label="操作">
          <n-button type="primary" @click="savePlayerSettings">
            保存播放器设置
          </n-button>
        </n-form-item>
      </div>

      <!-- 高级设置 -->
      <div class="advanced-section">
        <n-h3>高级设置</n-h3>
        <n-form-item label="操作">
          <div class="advanced-actions">
            <n-button
              ghost
              type="warning"
              @click="clearCache"
              :disabled="isProcessing"
            >
              清除缓存
            </n-button>
            <n-button
              type="error"
              @click="resetApp"
              :disabled="isProcessing"
            >
              重置应用
            </n-button>
          </div>
        </n-form-item>
      </div>
    </n-form>
  </div>
</template>

<script setup>
/**
 * ==================== 依赖导入 ====================
 */
import { ref, onMounted } from 'vue'

// API 函数
import {
  getOpenListStatus,
  startOpenList,
  stopOpenList,
  getConfig,
  updateConfig
} from '@/api/openlist'
import { apiUrl } from '@/api/request'

/**
 * ==================== 响应式状态 ====================
 */

// 暗色模式
const darkMode = ref(true)

// 通知开关
const notification = ref(false)

// 语言设置
const language = ref('zh-CN')

// 内置服务器设置
const serverEnabled = ref(false)
const serverPort = ref(5244)
const serverRunning = ref(false)
const serverUsername = ref('admin')
const serverPassword = ref('')
const showPassword = ref(false)
const isStarting = ref(false)
const isStopping = ref(false)
const isDownloading = ref(false)
const isProcessing = ref(false)
const autoStart = ref(false)

// 配置加载状态
const configLoaded = ref(false)

// 刮削设置
const doubanCookie = ref('')
const tmdbApiKey = ref('')

// 播放器设置
const playerSettings = ref({
  hwdec: 'auto-copy',
  enhancement_profile: 'original',
  frame_profile: 'off',
  subtitle_mode: 'auto',
  show_playback_info: true,
  always_on_top: false,
  volume: 80
})

const playerHwdecOptions = [
  { label: '自动（推荐）', value: 'auto-copy' },
  { label: '安全自动', value: 'auto-safe' },
  { label: '软件解码', value: 'no' }
]

const playerEnhancementOptions = [
  { label: '原画', value: 'original' },
  { label: '净化', value: 'clean' },
  { label: '锐化', value: 'sharp' },
  { label: '高清', value: 'clarity' },
  { label: '动漫 AI 超分 · 性能（Anime4K）', value: 'anime_light' },
  { label: '动漫 AI 超分 · 质量（Anime4K）', value: 'anime_strong' },
  { label: '通用 AI 超分 · 性能（FSRCNNX）', value: 'ai_general' },
  { label: '通用 AI 超分 · 质量（FSRCNNX）', value: 'ai_quality' }
]

const playerFrameOptions = [
  { label: '关闭', value: 'off' },
  { label: '自然', value: 'natural' },
  { label: '平滑', value: 'smooth' },
  { label: '显示插帧', value: 'display' }
]

const playerSubtitleOptions = [
  { label: '自动选择', value: 'auto' },
  { label: '默认关闭', value: 'off' }
]

/**
 * ==================== 语言选项 ====================
 */
const langOptions = [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' }
]

/**
 * ==================== 服务器操作方法 ====================
 */

/**
 * 加载配置
 */
async function loadConfig() {
  try {
    const config = await getConfig()
    serverEnabled.value = config.openlist_enabled || false
    serverPort.value = config.openlist_port || 5244
    autoStart.value = config.openlist_auto_start || false
    
    // 从 config API 获取用户名和密码（始终设置，确保有默认值）
    serverUsername.value = config.openlist_admin_username || config.openlist_username || 'admin'
    serverPassword.value = config.openlist_admin_password || config.openlist_password || ''
    
    // 加载刮削设置（优先使用驼峰命名字段）
    doubanCookie.value = config.doubanCookie || config.douban_cookie || ''
    tmdbApiKey.value = config.tmdbApiKey || config.tmdb_api_key || ''
    
    configLoaded.value = true
  } catch (error) {
    console.log('加载配置失败:', error)
    configLoaded.value = true
  }
}

async function loadPlayerSettings() {
  try {
    const response = await fetch(apiUrl('/settings/player'))
    const data = await response.json()
    if (data.code === 0 && data.data) {
      playerSettings.value = { ...playerSettings.value, ...data.data }
    }
  } catch (error) {
    console.log('加载播放器设置失败:', error)
  }
}

/**
 * 保存配置
 */
async function saveConfig() {
  try {
    await updateConfig({
      openlist_enabled: serverEnabled.value,
      openlist_port: serverPort.value,
      openlist_auto_start: autoStart.value
    })
  } catch (error) {
    console.log('保存配置失败:', error)
  }
}

/**
 * 获取服务器状态
 */
async function getServerStatus() {
  try {
    const status = await getOpenListStatus()
    serverRunning.value = status.status === 'running'
    if (status.port) {
      serverPort.value = status.port
    }
    // 从 status API 获取用户名和密码（优先从 status API 获取）
    serverUsername.value = status.admin_username || status.openlist_username || status.username || 'admin'
    serverPassword.value = status.admin_password || status.openlist_password || status.password || ''
  } catch (error) {
    console.log('获取服务器状态失败:', error)
  }
}

/**
 * 启动内置服务器
 */
async function startServer() {
  isStarting.value = true
  try {
    const result = await startOpenList()
    serverRunning.value = true
    if (result.port) {
      serverPort.value = result.port
    }
    if (result.admin_password) {
      serverPassword.value = result.admin_password
    }
    await getServerStatus()
  } catch (error) {
    alert('启动服务器失败：' + error.message)
  } finally {
    isStarting.value = false
  }
}

/**
 * 停止内置服务器
 */
async function stopServer() {
  isStopping.value = true
  try {
    await stopOpenList()
    serverRunning.value = false
  } catch (error) {
    alert('停止服务器失败：' + error.message)
  } finally {
    isStopping.value = false
  }
}

/**
 * 打开服务器地址
 */
function openServerUrl() {
  window.open(`http://localhost:${serverPort.value}`, '_blank')
}

/**
 * 复制密码到剪贴板
 */
async function copyPassword() {
  if (!serverPassword.value) return
  try {
    await navigator.clipboard.writeText(serverPassword.value)
    alert('密码已复制到剪贴板')
  } catch (error) {
    console.log('复制密码失败:', error)
    alert('复制失败，请手动复制')
  }
}

/**
 * 切换自动启动
 */
async function toggleAutoStart() {
  isProcessing.value = true
  try {
    autoStart.value = !autoStart.value
    await saveConfig()
    alert(autoStart.value ? '已开启自动启动' : '已取消自动启动')
  } catch (error) {
    alert('操作失败：' + error.message)
    autoStart.value = !autoStart.value
  } finally {
    isProcessing.value = false
  }
}

/**
 * 下载/更新服务器
 */
async function downloadServer() {
  isDownloading.value = true
  try {
    const response = await fetch(apiUrl('/openlist/download'), {
      method: 'POST'
    })
    const data = await response.json()
    if (data.code === 0 && data.data && data.data.success) {
      alert(data.data.message || '下载/更新成功')
    } else {
      alert(data.message || data.data?.message || '下载/更新失败')
    }
  } catch (error) {
    alert('下载/更新失败：' + error.message)
  } finally {
    isDownloading.value = false
  }
}

/**
 * 卸载服务器
 */
async function uninstallServer() {
  if (!confirm('确定要卸载 OpenList 服务器吗？此操作将删除相关文件。')) {
    return
  }
  isProcessing.value = true
  try {
    alert('卸载功能开发中...')
  } catch (error) {
    alert('卸载失败：' + error.message)
  } finally {
    isProcessing.value = false
  }
}

/**
 * 服务器启用状态变化处理
 */
async function onServerEnabledChange() {
  await saveConfig()
}

/**
 * 页面加载时获取配置和服务器状态
 */
async function init() {
  await loadConfig()
  await getServerStatus()
  await loadPlayerSettings()
}

init()

/**
 * ==================== 刮削设置方法 ====================
 */

/**
 * 保存刮削设置
 */
async function saveScraperSettings() {
  try {
    // 调用后端验证过的接口
    const response = await fetch(apiUrl('/settings/scraper'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        doubanCookie: doubanCookie.value,
        tmdbApiKey: tmdbApiKey.value
      })
    })
    const data = await response.json()
    if (data.code === 0) {
      alert('保存成功')
    } else {
      alert(data.message || '保存失败')
    }
  } catch (error) {
    alert('保存失败：' + error.message)
  }
}

async function savePlayerSettings() {
  try {
    const response = await fetch(apiUrl('/settings/player'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(playerSettings.value)
    })
    const data = await response.json()
    if (data.code === 0 && data.data) {
      playerSettings.value = { ...playerSettings.value, ...data.data }
      alert('播放器设置已保存。硬件解码、AI 超分和默认补帧会在下次打开播放器时生效。')
    } else {
      alert(data.message || '保存播放器设置失败')
    }
  } catch (error) {
    console.log('保存播放器设置失败:', error)
    alert('保存播放器设置失败，请稍后重试')
  }
}

/**
 * 清除缓存
 */
async function clearCache() {
  if (!confirm('确定要清除所有缓存吗？这将清除海报图片缓存和本地存储数据。')) {
    return
  }
  isProcessing.value = true
  try {
    // 清除前端缓存（sessionStorage 和 localStorage）
    sessionStorage.clear()
    localStorage.clear()
    
    // 清除后端缓存（图片缓存等）
    try {
      const response = await fetch(apiUrl('/cache/clear'), {
        method: 'POST'
      })
      const data = await response.json()
      if (data.code !== 0) {
        console.log('后端缓存清除失败:', data.message)
      }
    } catch (error) {
      console.log('后端缓存清除接口不可用:', error)
    }
    
    alert('缓存清除成功')
  } catch (error) {
    alert('清除缓存失败：' + error.message)
  } finally {
    isProcessing.value = false
  }
}

/**
 * 重置应用
 */
async function resetApp() {
  if (!confirm('确定要重置应用吗？这将清除所有设置和数据，恢复到初始状态。此操作不可撤销！')) {
    return
  }
  if (!confirm('再次确认：确定要重置应用吗？所有数据将被清除！')) {
    return
  }
  isProcessing.value = true
  try {
    // 清除前端缓存
    sessionStorage.clear()
    localStorage.clear()
    
    // 调用后端重置接口
    try {
      const response = await fetch(apiUrl('/reset'), {
        method: 'POST'
      })
      const data = await response.json()
      if (data.code !== 0) {
        console.log('后端重置失败:', data.message)
      }
    } catch (error) {
      console.log('后端重置接口不可用:', error)
    }
    
    // 刷新页面
    window.location.reload()
  } catch (error) {
    alert('重置应用失败：' + error.message)
    isProcessing.value = false
  }
}
</script>

<style scoped>
/* ==================== 页面样式 ==================== */
.settings-page {
  padding: 24px;
}

/* 开关标签样式 */
.switch-label {
  margin-left: 8px;
}

/* 语言选择器样式 */
.lang-select {
  width: 180px;
}

/* ==================== 服务器设置区域样式 ==================== */
.server-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.server-section :deep(.n-h3) {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

/* 端口输入框样式 */
.port-input {
  width: 120px;
}

.port-tip {
  margin-left: 12px;
  color: #9ca3af;
  font-size: 14px;
}

/* 状态指示器样式 */
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.stopped {
  background-color: #ef4444;
}

.status-dot.running {
  background-color: #22c55e;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.status-text {
  font-size: 14px;
}

.server-url {
  margin-left: 8px;
  padding: 4px 10px;
  background-color: #f3f4f6;
  border-radius: 4px;
  font-size: 13px;
  color: #3b82f6;
  font-family: monospace;
}

/* 凭证显示区域样式 */
.credential-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.credential-input {
  width: 200px;
}

/* 服务器操作按钮区域 */
.server-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* ==================== 刮削设置区域样式 ==================== */
.scraper-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.scraper-section :deep(.n-h3) {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

/* Cookie输入框样式 */
.cookie-input {
  width: 500px;
}

/* API密钥输入框样式 */
.api-key-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.api-key-input {
  width: 350px;
}

/* TMDB链接样式 */
.tmdb-link {
  padding: 8px 16px;
  background-color: #3b82f6;
  color: #ffffff;
  border-radius: 4px;
  text-decoration: none;
  font-size: 14px;
  transition: background-color 0.2s;
}

.tmdb-link:hover {
  background-color: #2563eb;
}

/* 输入提示文字 */
.input-tip {
  margin-top: 8px;
  color: #9ca3af;
  font-size: 13px;
}

/* ==================== 播放器设置区域样式 ==================== */
.player-section {
  margin-top: 32px;
  padding: 24px;
  border: 1px solid rgba(90, 135, 255, 0.18);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.055), rgba(139, 92, 246, 0.035));
}

.player-section :deep(.n-h3) {
  margin-bottom: 6px;
  font-size: 16px;
  font-weight: 600;
}

.player-description {
  margin: 0 0 18px;
  color: #9ca3af;
  font-size: 13px;
  line-height: 1.6;
}

.player-select {
  width: min(440px, 100%);
}

.player-volume-row {
  display: flex;
  align-items: center;
  width: min(360px, 100%);
  gap: 14px;
}

.player-volume-slider {
  flex: 1;
}

.player-volume-value {
  min-width: 42px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

/* ==================== 高级设置区域样式 ==================== */
.advanced-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.advanced-section :deep(.n-h3) {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.advanced-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
