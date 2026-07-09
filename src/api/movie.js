import { get, post, postForm, del } from './request'

/**
 * 电影相关 API
 */

// 获取首页数据
export function getHomeData(params = {}) {
  return get('/movies/home', params)
}

// 获取电影详情
export function getMovieDetail(id) {
  return get(`/movies/${id}`)
}

// 获取相关推荐
export function getRecommendations(id, limit = 8) {
  return get(`/movies/${id}/recommendations`, { limit })
}

// 获取播放地址
export function getPlayUrl(id) {
  return get(`/movies/${id}/play`)
}

// 获取收藏列表
export function getFavorites(params = {}) {
  return get('/movies/favorites', params)
}

// 添加收藏
export function addFavorite(id) {
  return post(`/movies/${id}/favorite`)
}

// 取消收藏
export function removeFavorite(id) {
  return del(`/movies/${id}/favorite`)
}

// 获取历史记录
export function getHistory(params = {}) {
  return get('/movies/history', params)
}

// 获取统计数据
export function getStats() {
  return get('/movies/stats')
}

// ==================== MPV 播放器控制 ====================
// MPV 模式下视频在后端 mpv 进程渲染，浏览器只能通过这些接口控制

/** 获取播放信息（含 playerType/playUrl/headers，仅供后端 mpv 使用） */
export function getPlayInfo(id, episodeId, playerType = 'mpv') {
  return get(`/movies/${id}/play`, { episode_id: episodeId, player_type: playerType })
}

/** 开始播放（让后端 mpv 启动播放） */
export function playerPlay(movieId, episodeId, position = 0) {
  return post('/player/play', null, {
    params: { movie_id: movieId, episode_id: episodeId, position }
  })
}

/** 暂停 */
export function playerPause() {
  return post('/player/pause')
}

/** 恢复 */
export function playerResume() {
  return post('/player/resume')
}

/** 停止 */
export function playerStop() {
  return post('/player/stop')
}

/** 跳转到指定位置（秒） */
export function playerSeek(position) {
  return post('/player/seek', null, { params: { position } })
}

/** 相对跳转（秒，可负） */
export function playerSeekRelative(seconds) {
  return post('/player/seek_relative', null, { params: { seconds } })
}

/** 设置音量 0-100 */
export function playerSetVolume(volume) {
  return post('/player/volume', null, { params: { volume } })
}

/** 设置静音 */
export function playerSetMute(mute) {
  return post('/player/mute', null, { params: { mute } })
}

/** 下一集 */
export function playerNext() {
  return post('/player/next')
}

/** 上一集 */
export function playerPrevious() {
  return post('/player/previous')
}

/** 读取播放器状态（轮询） */
export function playerGetStatus() {
  return get('/player/status')
}

// ==================== 在线视频 ====================

/** 浏览视频网站，获取层级结构 */
export function browseOnlineSite(url) {
  return post('/online/browse', { url })
}

/** 获取视频详细信息 */
export function getOnlineVideoDetail(url) {
  return post('/online/detail', { url })
}

/** 添加在线视频到库 */
export function addOnlineVideo(video) {
  return post('/online/add', { video })
}

/** 删除在线视频 */
export function removeOnlineVideo(videoId) {
  return del(`/online/${videoId}`)
}