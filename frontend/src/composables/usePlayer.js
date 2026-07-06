/**
 * 播放器全局状态（MPV 模式）
 *
 * 视频在后端 mpv 进程渲染，浏览器端只维护：
 *  - 播放会话信息（标题、剧集、剧集列表用于上下集）
 *  - 实时播放状态（state / time_pos / duration / volume / mute / speed）
 *  - 与后端 mpv 的轮询与控制命令
 *
 * 状态采用模块级 reactive 对象（ESM 单例），与 <PlayerBar /> 在 App.vue
 * 路由外层挂载配合，跨页面常驻。
 */
import { reactive, ref, computed } from 'vue'
import {
  playerPlay,
  playerPause,
  playerResume,
  playerStop,
  playerSeek,
  playerSetVolume,
  playerSetMute,
  playerGetStatus,
  getPlayInfo
} from '@/api/movie'

/* ==================== 共享状态 ==================== */

/** 会话信息（"现在在放什么"） */
export const playerSession = reactive({
  visible: false,        // 控制条是否显示
  movieId: '',
  movieTitle: '',
  episodeId: '',
  episodeTitle: '',
  cover: '',
  // 当前剧集所在系列的所有剧集列表（用于上下集导航）
  // 元素形如 { id, title, num }
  episodeList: [],
  seasonIndex: 0
})

/** 播放器实时状态（来自 /api/player/status） */
export const playerState = reactive({
  state: 'stopped',      // stopped | playing | paused
  timePos: 0,
  duration: 0,
  volume: 100,
  mute: false,
  speed: 1.0,
  title: '',
  loading: false,
  error: ''
})

/* ==================== 内部状态 ==================== */

let pollTimer = null
const POLL_INTERVAL = 1000

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const info = await playerGetStatus()
      Object.assign(playerState, {
        state: info.state || 'stopped',
        timePos: Number(info.time_pos) || 0,
        duration: Number(info.duration) || 0,
        volume: Number(info.volume) || 0,
        mute: Boolean(info.mute),
        speed: Number(info.speed) || 1.0,
        title: info.title || ''
      })
      // 后端停止后自动收起控制条
      if (playerState.state === 'stopped' && playerSession.visible) {
        // 保留 1.5s 让用户看到 "已停止" 状态再收起
        setTimeout(() => {
          if (playerState.state === 'stopped') {
            playerSession.visible = false
          }
        }, 1500)
      }
    } catch (err) {
      // 静默失败，不打断 UI
    }
  }, POLL_INTERVAL)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/* ==================== 派生数据 ==================== */

const currentEpisodeIndex = computed(() => {
  return playerSession.episodeList.findIndex(ep => ep.id === playerSession.episodeId)
})

export const hasPrev = computed(() => currentEpisodeIndex.value > 0)
export const hasNext = computed(() => {
  const i = currentEpisodeIndex.value
  return i >= 0 && i < playerSession.episodeList.length - 1
})

/* ==================== 公开方法 ==================== */

/**
 * 启动播放
 * @param {Object} options
 * @param {string} options.movieId      影片 ID
 * @param {string} options.movieTitle   影片标题
 * @param {string} options.episodeId    剧集 ID（电影可为空）
 * @param {string} options.episodeTitle 剧集标题
 * @param {string} options.cover        海报/封面 URL
 * @param {Array}  options.episodeList  同系列所有剧集 [{id, title, num}]
 * @param {number} options.seasonIndex  季索引
 * @param {number} options.position     起始位置（秒）
 */
export async function startPlay({
  movieId,
  movieTitle,
  episodeId = '',
  episodeTitle = '',
  cover = '',
  episodeList = [],
  seasonIndex = 0,
  position = 0
}) {
  if (!movieId) {
    playerState.error = '缺少 movieId'
    return
  }

  playerState.loading = true
  playerState.error = ''

  // 1) 获取播放信息（playerType=mpv）—— 仅用于校验数据源可用
  //    不再使用返回的 playUrl 直接 window.open，那是后端 mpv 用的
  try {
    await getPlayInfo(movieId, episodeId, 'mpv')
  } catch (err) {
    playerState.loading = false
    playerState.error = err.message || '获取播放信息失败'
    return
  }

  // 2) 写入会话信息
  //    visible 保持 false —— 不在浏览器底部弹出控制条，
  //    后端 mpv 自己开窗，所有控制（暂停/进度/音量）由 mpv 自带窗口处理
  Object.assign(playerSession, {
    visible: false,
    movieId,
    movieTitle: movieTitle || '',
    episodeId: episodeId || '',
    episodeTitle: episodeTitle || '',
    cover: cover || '',
    episodeList: Array.isArray(episodeList) ? episodeList : [],
    seasonIndex: seasonIndex || 0
  })

  // 3) 通知后端 mpv 启动播放
  try {
    await playerPlay(movieId, episodeId, position)
  } catch (err) {
    playerState.error = err.message || '启动播放失败'
    playerState.loading = false
    return
  }

  playerState.loading = false
  // 不再启动前端轮询 —— 浏览器不显示控制条，没必要每 1s 拉一次状态
}

export async function pause() {
  try { await playerPause() } catch (e) { playerState.error = e.message }
}

export async function resume() {
  try { await playerResume() } catch (e) { playerState.error = e.message }
}

export async function stop() {
  stopPolling()
  try { await playerStop() } catch (e) { /* ignore */ }
  playerSession.visible = false
  // 重置会话
  playerSession.movieId = ''
  playerSession.episodeId = ''
  playerSession.episodeList = []
  Object.assign(playerState, {
    state: 'stopped',
    timePos: 0,
    duration: 0
  })
}

export async function seek(position) {
  try { await playerSeek(position) } catch (e) { playerState.error = e.message }
}

export async function setVolume(volume) {
  const v = Math.max(0, Math.min(100, Math.round(volume)))
  // 本地立即更新，避免后端往返延迟
  playerState.volume = v
  try { await playerSetVolume(v) } catch (e) { playerState.error = e.message }
}

export async function toggleMute() {
  const next = !playerState.mute
  playerState.mute = next
  try { await playerSetMute(next) } catch (e) { playerState.error = e.message }
}

/**
 * 播放上一集 / 下一集
 * @param {'prev'|'next'} direction
 */
export async function switchEpisode(direction) {
  const list = playerSession.episodeList
  if (!list.length) return
  const idx = currentEpisodeIndex.value
  const target = direction === 'next' ? list[idx + 1] : list[idx - 1]
  if (!target) return
  await startPlay({
    movieId: target.movieId || playerSession.movieId,
    movieTitle: playerSession.movieTitle,
    episodeId: target.id,
    episodeTitle: target.title,
    cover: playerSession.cover,
    episodeList: list,
    seasonIndex: playerSession.seasonIndex
  })
}

/**
 * 关闭控制条（不影响后端 mpv 实际播放）
 */
export function closeBar() {
  playerSession.visible = false
}

/**
 * 格式化秒为 mm:ss / hh:mm:ss
 */
export function formatTime(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(r)}` : `${pad(m)}:${pad(r)}`
}

/* ==================== 复合暴露 ==================== */

export function usePlayer() {
  return {
    session: playerSession,
    state: playerState,
    hasPrev,
    hasNext,
    startPlay,
    pause,
    resume,
    stop,
    seek,
    setVolume,
    toggleMute,
    switchEpisode,
    closeBar,
    formatTime
  }
}
