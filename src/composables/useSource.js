import { ref, onMounted } from 'vue'
import { getSources, addSource, updateSource, deleteSource, browseDirectory, rescanSource } from '@/api/source'

/**
 * 数据源管理组合式函数
 */
export function useSource() {
  const sources = ref([])
  const loading = ref(false)
  const error = ref('')
  const browsing = ref(false)
  const browseItems = ref([])
  const currentPath = ref('/')

  // 加载数据源列表
  async function loadSources() {
    loading.value = true
    error.value = ''

    try {
      const data = await getSources()
      sources.value = Array.isArray(data) ? data : []
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载数据源失败'
      sources.value = []
    } finally {
      loading.value = false
    }
  }

  // 添加数据源
  async function addNewSource(sourceData) {
    try {
      await addSource(sourceData)
      await loadSources()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : '添加数据源失败'
      return false
    }
  }

  // 更新数据源
  async function updateExistingSource(id, sourceData) {
    try {
      await updateSource(id, sourceData)
      await loadSources()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : '更新数据源失败'
      return false
    }
  }

  // 删除数据源
  async function deleteExistingSource(id) {
    try {
      await deleteSource(id)
      await loadSources()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : '删除数据源失败'
      return false
    }
  }

  // 浏览目录
  async function browse(path = '/', sourceData = {}) {
    browsing.value = true
    currentPath.value = path

    try {
      const params = { path, ...sourceData }
      const data = await browseDirectory(params)
      browseItems.value = Array.isArray(data) ? data : []
    } catch (err) {
      error.value = err instanceof Error ? err.message : '浏览目录失败'
      browseItems.value = []
    } finally {
      browsing.value = false
    }
  }

  // 重扫数据源
  async function rescan(id) {
    try {
      await rescanSource(id)
      await loadSources()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : '重扫失败'
      return false
    }
  }

  // 初始化加载
  onMounted(loadSources)

  return {
    sources,
    loading,
    error,
    browsing,
    browseItems,
    currentPath,
    loadSources,
    addNewSource,
    updateExistingSource,
    deleteExistingSource,
    browse,
    rescan
  }
}