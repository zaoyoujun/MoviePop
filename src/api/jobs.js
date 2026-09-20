import { get, post } from './request'

/**
 * 后台任务 API
 * 对应后端 scheduler.py 的定时/手动任务，前端用于进度轮询与手动触发。
 */

// 查询后台任务进度（首次引导页轮询用）
export function getJobsStatus() {
  return get('/jobs/status')
}

// 手动触发 trending 刷新
export function refreshTrending() {
  return post('/jobs/refresh/trending')
}

// 手动触发热度刷新
export function refreshHotness() {
  return post('/jobs/refresh/hotness')
}

// 手动触发全量刷新（首次下载或重置）
export function refreshAll() {
  return post('/jobs/refresh/all')
}

// 请求取消后台任务（已写入的数据保留，任务在每轮循环自行结束）
export function cancelJob(task) {
  return post(`/jobs/cancel/${task}`)
}
