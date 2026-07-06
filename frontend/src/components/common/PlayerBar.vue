<!--
  MPV 播放器控制条（全局组件）

  视频在后端 mpv 进程渲染，浏览器只显示控制 UI：
  - 进度条 / 播放暂停 / 上下集 / 音量 / 关闭
  - 状态来自 usePlayer 提供的轮询数据
  - 跨页面常驻（在 App.vue 路由外挂载）
-->
<template>
  <transition name="player-bar-fade">
    <div v-if="session.visible" class="player-bar" :class="`player-bar-${state.state}`">
      <!-- 左侧：封面 + 标题信息 -->
      <div class="player-info">
        <div class="player-cover">
          <img v-if="session.cover" :src="session.cover" :alt="session.movieTitle" />
          <div v-else class="player-cover-placeholder">
            <span>🎬</span>
          </div>
        </div>
        <div class="player-meta">
          <div class="player-title" :title="session.movieTitle">
            {{ session.movieTitle || '未知影片' }}
          </div>
          <div class="player-episode" :title="session.episodeTitle">
            <template v-if="session.episodeTitle">
              {{ session.episodeTitle }}
            </template>
            <template v-else>电影</template>
          </div>
        </div>
      </div>

      <!-- 中部：进度 + 控制按钮 -->
      <div class="player-center">
        <div class="player-controls">
          <button
            class="ctrl-btn"
            :disabled="!hasPrev"
            :title="hasPrev ? '上一集' : '已是第一集'"
            @click="switchEpisode('prev')"
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z" fill="currentColor" />
            </svg>
          </button>
          <button
            class="ctrl-btn ctrl-btn-primary"
            :title="state.state === 'playing' ? '暂停' : '播放'"
            @click="togglePlay"
          >
            <svg v-if="state.state === 'playing'" viewBox="0 0 24 24" width="22" height="22">
              <path d="M6 5h4v14H6V5zm8 0h4v14h-4V5z" fill="currentColor" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="22" height="22">
              <path d="M8 5v14l11-7L8 5z" fill="currentColor" />
            </svg>
          </button>
          <button
            class="ctrl-btn"
            :disabled="!hasNext"
            :title="hasNext ? '下一集' : '已是最后一集'"
            @click="switchEpisode('next')"
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M6 18l8.5-6L6 6v12zM16 6h2v12h-2V6z" fill="currentColor" />
            </svg>
          </button>
          <button class="ctrl-btn" title="停止播放" @click="stop">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" />
            </svg>
          </button>
        </div>
        <div class="player-progress">
          <span class="time-text">{{ formatTime(state.timePos) }}</span>
          <div class="progress-bar" @click="onProgressClick" ref="progressRef">
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
          </div>
          <span class="time-text">{{ formatTime(state.duration) }}</span>
        </div>
      </div>

      <!-- 右侧：音量 + 关闭 -->
      <div class="player-right">
        <div class="volume-control">
          <button
            class="ctrl-btn ctrl-btn-sm"
            :title="state.mute ? '取消静音' : '静音'"
            @click="toggleMute"
          >
            <svg v-if="state.mute || state.volume === 0" viewBox="0 0 24 24" width="20" height="20">
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" fill="currentColor" />
            </svg>
            <svg v-else-if="state.volume < 50" viewBox="0 0 24 24" width="20" height="20">
              <path d="M7 9v6h4l5 5V4l-5 5H7z" fill="currentColor" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="20" height="20">
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="currentColor" />
            </svg>
          </button>
          <div class="volume-slider" @click="onVolumeClick" ref="volumeRef">
            <div class="volume-track">
              <div class="volume-fill" :style="{ width: (state.mute ? 0 : state.volume) + '%' }"></div>
            </div>
          </div>
        </div>
        <button class="ctrl-btn ctrl-btn-sm" title="收起控制条（不影响后端播放）" @click="closeBar">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor" />
          </svg>
        </button>
      </div>

      <!-- 状态徽章 -->
      <div v-if="state.loading || state.error" class="player-badge">
        <span v-if="state.error" class="badge badge-error" :title="state.error">启动失败</span>
        <span v-else class="badge badge-loading">启动中…</span>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  playerSession,
  playerState,
  hasPrev,
  hasNext,
  pause,
  resume,
  stop,
  seek,
  setVolume,
  toggleMute,
  switchEpisode,
  closeBar,
  formatTime
} from '@/composables/usePlayer'

const session = playerSession
const state = playerState

const progressRef = ref(null)
const volumeRef = ref(null)

const progressPercent = computed(() => {
  if (!state.duration || state.duration <= 0) return 0
  return Math.max(0, Math.min(100, (state.timePos / state.duration) * 100))
})

async function togglePlay() {
  if (state.state === 'playing') {
    await pause()
  } else if (state.state === 'paused') {
    await resume()
  } else {
    // stopped → 重新启动当前会话
    if (session.episodeId) {
      await switchEpisode('next').catch(() => {})  // 触发不到 next
    }
  }
}

function onProgressClick(e) {
  if (!progressRef.value || !state.duration) return
  const rect = progressRef.value.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  seek(ratio * state.duration)
}

function onVolumeClick(e) {
  if (!volumeRef.value) return
  const rect = volumeRef.value.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  setVolume(ratio * 100)
}
</script>

<style scoped>
.player-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9998;
  display: grid;
  grid-template-columns: 280px 1fr 240px;
  align-items: center;
  gap: 24px;
  padding: 12px 24px;
  background: linear-gradient(180deg, rgba(15, 18, 30, 0.95), rgba(10, 12, 22, 0.98));
  border-top: 1px solid rgba(105, 240, 198, 0.25);
  backdrop-filter: blur(20px);
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.4);
  color: #f6f8ff;
}

.player-bar-playing {
  border-top-color: rgba(105, 240, 198, 0.45);
}

.player-bar-paused {
  border-top-color: rgba(255, 200, 100, 0.45);
}

/* ============ 左侧 ============ */
.player-info {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.player-cover {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
}

.player-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.player-cover-placeholder {
  font-size: 24px;
  opacity: 0.6;
}

.player-meta {
  min-width: 0;
}

.player-title {
  font-size: 14px;
  font-weight: 600;
  color: #f6f8ff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.player-episode {
  font-size: 12px;
  color: #98a4b8;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

/* ============ 中部 ============ */
.player-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.player-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ctrl-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  color: #f6f8ff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ctrl-btn:hover:not(:disabled) {
  background: rgba(105, 240, 198, 0.2);
  color: #69f0c6;
}

.ctrl-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.ctrl-btn-primary {
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
  color: #06121a;
}

.ctrl-btn-primary:hover {
  filter: brightness(1.1);
  color: #06121a;
}

.ctrl-btn-sm {
  width: 32px;
  height: 32px;
}

.player-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  max-width: 600px;
}

.time-text {
  font-size: 12px;
  color: #98a4b8;
  font-variant-numeric: tabular-nums;
  min-width: 48px;
  text-align: center;
}

.progress-bar {
  flex: 1;
  height: 16px;
  display: flex;
  align-items: center;
  cursor: pointer;
}

.progress-track {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 2px;
  position: relative;
  overflow: hidden;
  transition: height 0.15s ease;
}

.progress-bar:hover .progress-track {
  height: 6px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #69f0c6, #32c6ff);
  border-radius: 2px;
  transition: width 0.3s linear;
}

/* ============ 右侧 ============ */
.player-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 6px;
}

.volume-slider {
  width: 80px;
  height: 16px;
  display: flex;
  align-items: center;
  cursor: pointer;
}

.volume-track {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 2px;
  position: relative;
  overflow: hidden;
}

.volume-fill {
  height: 100%;
  background: #69f0c6;
  border-radius: 2px;
  transition: width 0.1s ease;
}

/* ============ 状态徽章 ============ */
.player-badge {
  position: absolute;
  top: -10px;
  left: 24px;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.badge-loading {
  background: rgba(50, 198, 255, 0.2);
  color: #32c6ff;
  border: 1px solid rgba(50, 198, 255, 0.4);
}

.badge-error {
  background: rgba(255, 99, 132, 0.2);
  color: #ff6384;
  border: 1px solid rgba(255, 99, 132, 0.4);
}

/* ============ 入场动画 ============ */
.player-bar-fade-enter-active,
.player-bar-fade-leave-active {
  transition: all 0.3s ease;
}

.player-bar-fade-enter-from {
  opacity: 0;
  transform: translateY(100%);
}

.player-bar-fade-leave-to {
  opacity: 0;
  transform: translateY(100%);
}

/* ============ 响应式 ============ */
@media (max-width: 900px) {
  .player-bar {
    grid-template-columns: 1fr auto;
    gap: 12px;
    padding: 10px 16px;
  }
  .player-center {
    grid-column: 1 / -1;
    order: 3;
  }
  .volume-control {
    display: none;
  }
}
</style>
