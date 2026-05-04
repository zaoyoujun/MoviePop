import { ref, onUnmounted } from 'vue'
import type { JobStatus } from '../types/config'
import api from '../api/index'

export function useJobPolling() {
  const job = ref<JobStatus | null>(null)
  const polling = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  async function startPolling(jobId: string) {
    polling.value = true
    job.value = { job_id: jobId, name: '', status: 'running', current: 0, total: 0, message: '', error: '', result: null }

    async function poll() {
      try {
        const { data } = await api.get(`/api/jobs/${jobId}`)
        job.value = data
        if (data.status === 'completed' || data.status === 'failed') {
          polling.value = false
          return
        }
        timer = setTimeout(poll, 1000)
      } catch {
        polling.value = false
      }
    }

    await poll()
  }

  function stopPolling() {
    polling.value = false
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  onUnmounted(stopPolling)

  return { job, polling, startPolling, stopPolling }
}
