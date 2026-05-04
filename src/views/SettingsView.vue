<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAppStore } from '../stores/app'
import { fetchConfig, saveConfig, testConnection } from '../api/config'
import type { AppConfig } from '../types/config'
import { useTheme } from '../composables/useTheme'

const appStore = useAppStore()
const { theme, setTheme } = useTheme()

const config = ref<AppConfig | null>(null)
const loading = ref(true)
const saving = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)

onMounted(async () => {
  try {
    config.value = await fetchConfig()
  } finally {
    loading.value = false
  }
})

async function handleSave() {
  if (!config.value) return
  saving.value = true
  try {
    config.value = await saveConfig(config.value)
    appStore.bootstrap()
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  if (!config.value) return
  testResult.value = null
  testResult.value = await testConnection(config.value)
}
</script>

<template>
  <div class="settings-view">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="config" class="settings-content">
      <!-- 主题设置 -->
      <section class="settings-section">
        <h3>界面主题</h3>
        <div class="theme-grid">
          <button
            v-for="t in appStore.availableThemes"
            :key="t"
            class="theme-option"
            :class="{ active: theme === t }"
            @click="setTheme(t)"
          >
            {{ t }}
          </button>
        </div>
      </section>

      <!-- 媒体源设置 -->
      <section class="settings-section">
        <h3>媒体源</h3>
        <div class="form-group">
          <label>
            <span>远程源类型</span>
            <select v-model="config.remote_provider">
              <option value="webdav">WebDAV</option>
              <option value="openlist">OpenList</option>
            </select>
          </label>
        </div>
        <div class="form-group" v-if="config.remote_provider === 'webdav'">
          <label>
            <span>WebDAV 地址</span>
            <input v-model="config.webdav_host" placeholder="http://example.com/dav">
          </label>
          <label>
            <span>用户名</span>
            <input v-model="config.webdav_user">
          </label>
          <label>
            <span>密码</span>
            <input v-model="config.webdav_pass" type="password">
          </label>
        </div>
        <div class="form-actions">
          <button class="ghost-btn" @click="handleTest">测试连接</button>
          <span v-if="testResult" :class="testResult.success ? 'success' : 'error'">
            {{ testResult.message }}
          </span>
        </div>
      </section>

      <!-- 播放器设置 -->
      <section class="settings-section">
        <h3>播放器</h3>
        <div class="form-group">
          <label>
            <span>默认播放器</span>
            <select v-model="config.default_player">
              <option value="potplayer">PotPlayer</option>
              <option value="vlc">VLC</option>
            </select>
          </label>
          <label>
            <span>PotPlayer 路径</span>
            <input v-model="config.potplayer_path" placeholder="C:\...\PotPlayerMini64.exe">
          </label>
          <label>
            <span>VLC 路径</span>
            <input v-model="config.vlc_path" placeholder="C:\...\vlc.exe">
          </label>
        </div>
      </section>

      <!-- TMDB 设置 -->
      <section class="settings-section">
        <h3>元数据刮削</h3>
        <div class="form-group">
          <label>
            <span>TMDB API Key</span>
            <input v-model="config.tmdb_api_key" placeholder="输入你的 TMDB API Key">
          </label>
          <label>
            <span>自动刮削</span>
            <select v-model="config.enable_auto_scrape">
              <option :value="true">开启</option>
              <option :value="false">关闭</option>
            </select>
          </label>
        </div>
      </section>

      <div class="form-actions sticky-actions">
        <button class="primary-btn" @click="handleSave" :disabled="saving">
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading { text-align: center; padding: 40px; color: var(--text-faint); }
.settings-content { display: flex; flex-direction: column; gap: 24px; max-width: 640px; }
.settings-section {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 20px;
}
.settings-section h3 { margin: 0 0 16px; font-size: 16px; color: var(--text); }
.theme-grid { display: flex; gap: 10px; }
.theme-option {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  background: var(--panel-muted);
  color: var(--text-soft);
  font-size: 13px;
  text-transform: capitalize;
}
.theme-option.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.form-group { display: flex; flex-direction: column; gap: 12px; }
.form-group label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text-soft); }
.form-group input, .form-group select { padding: 8px 12px; font-size: 13px; }
.form-actions { display: flex; gap: 12px; align-items: center; margin-top: 12px; }
.ghost-btn {
  background: transparent;
  border: 1px solid var(--border);
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-soft);
}
.primary-btn {
  background: var(--accent);
  color: #fff;
  padding: 10px 24px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 14px;
}
.primary-btn:disabled { opacity: 0.6; }
.success { color: var(--success); font-size: 13px; }
.error { color: var(--danger); font-size: 13px; }
.sticky-actions { position: sticky; bottom: 0; padding: 12px 0; }
</style>
