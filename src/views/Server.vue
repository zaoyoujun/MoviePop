﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿/**
 * 服务器管理页面
 *
 * 功能模块：
 * 1. ServerHeader - 页面头部（标题、添加按钮、类型选择）
 * 2. SourceGrid - 数据源网格（展示所有数据源卡片）
 * 3. AddSourceModal - 添加数据源弹窗
 * 4. BrowseModal - 目录浏览弹窗
 *
 * 使用组件：
 * - ServerHeader: 页面头部组件
 * - SourceGrid: 数据源网格组件
 * - AddSourceModal: 添加数据源弹窗组件
 * - BrowseModal: 目录浏览弹窗组件
 */
<template>
  <main class="server-page">
    <!-- ==================== 页面头部 ==================== -->
    <ServerHeader
      :show-type-picker="showTypePicker"
      :source-options="sourceOptions"
      @toggle-type-picker="toggleTypePicker"
      @select-type="openSourceForm"
    />

    <!-- ==================== 数据源网格 ==================== -->
    <SourceGrid
      :sources="sources"
      :opened-menu="openedMenu"
      @toggle-menu="toggleMenu"
      @edit="openEditModal"
      @rescan="handleRescan"
      @delete="handleDelete"
    />

    <!-- ==================== 添加数据源弹窗 ==================== -->
    <AddSourceModal
      v-model="showAddModal"
      :form-data="sourceForm"
      :selected-paths="selectedPaths"
      :is-browsing="browsing"
      @verify="verifySource" @submit="addSource" :verifying="verifying"
      @browse="browseDirectory"
      @remove-path="removeFromSelectedPaths"
    />

    <!-- ==================== 编辑数据源弹窗 ==================== -->
    <AddSourceModal
      v-model="showEditModal"
      :form-data="editForm"
      :selected-paths="selectedPaths"
      :is-browsing="browsing"
      :is-edit="true"
      @verify="verifySource" @submit="editSource" :verifying="verifying"
      @browse="browseDirectory"
      @remove-path="removeFromSelectedPaths"
    />

    <!-- ==================== 目录浏览弹窗 ==================== -->
    <BrowseModal
      v-model="showBrowseModal"
      :current-path="currentPath"
      :items="browseItems"
      :is-multi-select="isMultiSelect"
      :selected-paths="selectedPaths"
      @update:is-multi-select="isMultiSelect = $event"
      @go-back="goBack"
      @browse="browseDirectory"
      @toggle-select="toggleSelect"
      @select="selectPath"
      @clear-selection="clearSelection"
      @confirm="confirmSelection"
    />

    <!-- 扫描进度 Toast 已在 App.vue 中全局挂载，此处不再重复渲染 -->
  </main>
</template>

<script setup>
/**
 * ==================== 依赖导入 ====================
 */
import { computed, onActivated, onMounted, reactive, ref, watch } from 'vue'

// Server page components.
import {
  ServerHeader,
  SourceGrid,
  AddSourceModal,
  BrowseModal
} from '@/components/server'

// API 函数
import {
  getSources,
  addSource as apiAddSource,
  updateSource as apiUpdateSource,
  deleteSource as apiDeleteSource,
  verifySource as apiVerifySource,
  browseDirectory as apiBrowseDirectory,
  getScanStatus,
  rescanSource as apiRescanSource,
  mountOpenList
} from '@/api/source'

import {
  getOpenListStatus,
  getConfig
} from '@/api/openlist'

// 模拟数据
import { MOCK_DATA } from '@/api/mockData'

// 全局扫描进度 Toast（模块单例，跨页面常驻）
import { scanToast, showScanToast, hideScanToast } from '@/composables/useScanToast'

/**
 * ==================== 常量定义 ====================
 */

/**
 * ==================== 状态定义 ====================
 */

// 数据源列表
const sources = ref([])

// 菜单状态
const openedMenu = ref('')

// 类型选择器
const showTypePicker = ref(false)

// 添加弹窗
const showAddModal = ref(false)

// 浏览弹窗
const showBrowseModal = ref(false)

// 浏览状态
const browsing = ref(false)
const browseItems = ref([])
const currentPath = ref('/')
const selectedPaths = ref([])
const isMultiSelect = ref(true)

// 编辑弹窗
const showEditModal = ref(false)
const editingSourceId = ref('')

// 验证状态
const verifying = ref(false)

// 内置服务器配置状态
const openlistEnabled = ref(false)
const openlistRunning = ref(false)

/**
 * 验证数据源连接
 */
async function verifySource() {
  // 编辑弹窗和新建弹窗共用此回调；不能固定读取新建表单，
  // 否则编辑 WebDAV 时会把空的 type/host 发给后端。
  const form = showEditModal.value ? editForm : sourceForm

  if (form.type === 'WebDAV' && !form.host.trim()) {
    alert('请先输入主机地址')
    return
  }

  // 内置OpenList需要选择驱动
  if (form.type === '内置OpenList' && !form.driver.trim()) {
    alert('请先选择存储驱动')
    return
  }

  verifying.value = true

  try {
    // 构建验证请求参数
    const verifyData = {
      type: apiSourceType(form.type),
      host: form.host.trim(),
      port: form.port || '',
      protocol: form.protocol,
      username: form.username || '',
      password: form.password || '',
      driver: form.driver || '',
      driver_type: form.driver_type || form.driver || '',
      cookie: (form.cookie || '').trim()
    }
    // 密码不会通过列表接口返回。编辑已保存的 WebDAV 时让后端按 ID
    // 复用保存的密码，避免仅调整目录就变成匿名连接。
    if (showEditModal.value && form.type === 'WebDAV' && editingSourceId.value) {
      verifyData.source_id = editingSourceId.value
    }
    Object.assign(verifyData, collectOpenListFields(form))

    const data = await apiVerifySource(verifyData)
    if (data?.ok !== false) {
      alert('连接成功！')
    } else {
      alert(data?.message || '连接失败')
    }
  } catch (error) {
    console.log('验证连接失败', error)
    alert(error?.message || '连接失败')
  } finally {
    verifying.value = false
  }
}

/**
 * ==================== 表单数据 ====================
 */

// Add source form.
const sourceForm = reactive({
  name: '',
  type: '',
  host: '',
  port: '',
  protocol: 'http',
  username: '',
  password: '',
  path: '',
  driver: '',
  cookie: '',
  mountPath: '',
  rootPath: ''
})

// 编辑表单
const editForm = reactive({
  name: '',
  type: '',
  host: '',
  port: '',
  protocol: 'http',
  username: '',
  password: '',
  path: '',
  driver: '',
  cookie: '',
  mountPath: '',
  rootPath: ''  // 自定义根路径
})

/**
 * ==================== 配置选项 ====================
 */

// 数据源类型选项（响应式计算属性，根据内置服务器状态决定是否禁用）
const sourceOptions = computed(() => [
  { 
    label: '内置OpenList',
    value: '内置OpenList',
    disabled: !openlistRunning.value,
    badge: openlistRunning.value ? '已就绪' : undefined
  },
  { label: 'WebDAV', value: 'WebDAV', disabled: false },
  { label: '本地目录', value: '本地存储', disabled: false },
  { label: '待开发', value: 'developing', disabled: true }
])

// 卡片颜色
const tintOptions = [
  'rgba(111, 110, 142, 0.62)',
  'rgba(95, 30, 30, 0.68)',
  'rgba(45, 83, 102, 0.66)',
  'rgba(91, 47, 116, 0.68)',
  'rgba(39, 98, 82, 0.66)',
  'rgba(101, 74, 38, 0.68)'
]

/**
 * ==================== 生命周期 ====================
 */
onMounted(() => {
  loadSources()
  refreshOpenListState()
})

onActivated(() => {
  refreshOpenListState()
})

/**
 * ==================== 方法 ====================
 */

/**
 * 加载数据源列表
 */
async function loadSources() {
  try {
    const sourcesData = await getSources()
    sources.value = Array.isArray(sourcesData) ? sourcesData : []
  } catch (error) {
    console.log('API 不可用，使用模拟数据进行演示')
    sources.value = MOCK_DATA.sources
  }
}

/**
 * 加载配置（获取内置服务器启用状态）
 */
async function refreshOpenListState() {
  try {
    const config = await getConfig()
    openlistEnabled.value = config.openlist_enabled || false
  } catch (error) {
    console.log('加载配置失败:', error)
    openlistEnabled.value = false
  }

  await checkOpenListStatus()
}

async function loadConfig() {
  await refreshOpenListState()
}
/**
 * 获取OpenList服务器运行状态
 */
async function checkOpenListStatus() {
  try {
    const status = await getOpenListStatus()
    console.log('OpenList status:', status)
    // 判断是否允许选择"内置 OpenList"
    // 只要服务器在运行状态就可以选择（是否登录是后续添加驱动时判断）
    openlistRunning.value =
      status.status === 'running' ||
      status.can_mount === true ||
      status.ready === true ||
      status.running === true
  } catch (error) {
    console.log('获取OpenList状态失败:', error)
    openlistRunning.value = false
  }
}

function apiSourceType(type) {
  const text = String(type || '')
  if (text === 'WebDAV') return 'webdav'
  if (text.toLowerCase().includes('openlist')) return 'openlist'
  if (text.includes('本地') || text.toLowerCase().includes('local')) return 'local'
  return text.toLowerCase()
}

function collectOpenListFields(form) {
  const keys = [
    'cookie',
    'refresh_token',
    'root_folder_id',
    'root_folder_path',
    'drive_type',
    'base_url',
    'token',
    'address',
    'username',
    'password'
  ]
  const payload = {}
  for (const key of keys) {
    const value = form[key]
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      payload[key] = String(value).trim()
    }
  }
  return payload
}

function defaultOpenListMountPath(driver) {
  const map = {
    quark: '/quark',
    aliyun: '/aliyun',
    '115': '/115',
    baidu: '/baidu',
    webdav: '/webdav'
  }
  return map[driver] || '/openlist'
}

/**
 * 切换菜单
 * @param {string} id - 数据源ID
 */
function toggleMenu(id) {
  openedMenu.value = openedMenu.value === id ? '' : id
}

/**
 * 切换类型选择器
 */
async function toggleTypePicker() {
  const nextVisible = !showTypePicker.value
  if (nextVisible) {
    await refreshOpenListState()
  }
  showTypePicker.value = nextVisible
}

/**
 * 打开添加表单
 * @param {Object} option - 数据源类型选项
 */
function openSourceForm(option) {
  if (option.value === 'developing') return

  if (option.value === '内置OpenList' && option.disabled) {
    alert('内置OpenList服务器尚未运行。\n\n请先前往「设置」页面：\n1. 开启内置服务器功能\n2. 启动服务器\n\n启动成功后即可在此挂载网盘目录。')
    return
  }

  // 重置表单
  sourceForm.name = option.label
  sourceForm.type = option.value
  sourceForm.host = ''
  sourceForm.port = ''
  sourceForm.protocol = 'http'
  sourceForm.username = ''
  sourceForm.password = ''
  sourceForm.path = ''
  sourceForm.driver = ''
  sourceForm.cookie = ''
  sourceForm.mountPath = option.value === '内置OpenList' ? '/openlist' : ''

  // 清空挂载路径
  selectedPaths.value = []

  showTypePicker.value = false
  showAddModal.value = true
}

/**
 * 添加数据源
 */
async function addSource() {
  // 验证表单
  if (!sourceForm.name.trim()) {
    alert('请输入数据源名称')
    return
  }

  if (sourceForm.type === '内置OpenList' && !sourceForm.driver) {
    alert('请选择存储驱动')
    return
  }

  if ((sourceForm.type === 'WebDAV' || sourceForm.type === '内置OpenList' || sourceForm.type === '本地存储') && selectedPaths.value.length === 0) {
    alert('请选择挂载目录')
    return
  }

  try {
    // 构建请求参数
    const sourceData = {
      name: sourceForm.name.trim(),
      type: apiSourceType(sourceForm.type),
      auto_scan: true
    }

    if (sourceForm.type === '内置OpenList') {
      // 使用 OpenList 挂载接口
      sourceData.driver = sourceForm.driver
      sourceData.driver_type = sourceForm.driver_type || sourceForm.driver
      sourceData.cookie = (sourceForm.cookie || '').trim()
      sourceData.mount_path = sourceForm.mountPath || defaultOpenListMountPath(sourceForm.driver)
      sourceData.selected_paths = selectedPaths.value
      Object.assign(sourceData, collectOpenListFields(sourceForm))
      
      const result = await mountOpenList(sourceData)
      await loadSources()
      showAddModal.value = false
      if (result.source?.id) {
        await handleRescan(result.source.id)
      }
    } else if (sourceForm.type === 'WebDAV') {
      const port = sourceForm.port ? `:${sourceForm.port}` : ''
      const firstPath = selectedPaths.value[0] || ''
      const cleanFirstPath = firstPath.replace(/^\/+/, '')
      const mainPath = cleanFirstPath ? '/' + cleanFirstPath.split('/').map(encodeURIComponent).join('/') : ''
      
      sourceData.host = sourceForm.host.trim()
      sourceData.port = sourceForm.port || ''
      sourceData.protocol = sourceForm.protocol
      sourceData.username = sourceForm.username || ''
      sourceData.password = sourceForm.password || ''
      sourceData.path = `${sourceForm.protocol}://${sourceForm.host}${port}${mainPath}`
      sourceData.selected_paths = selectedPaths.value
      
      const result = await apiAddSource(sourceData)
      await loadSources()
      showAddModal.value = false
      if (result.source?.id) {
        await handleRescan(result.source.id)
      }
    } else {
      // 本地存储类型类型
      sourceData.path = selectedPaths.value.join(',')
      sourceData.selected_paths = selectedPaths.value
      
      const result = await apiAddSource(sourceData)
      await loadSources()
      showAddModal.value = false
      if (result.source?.id) {
        await handleRescan(result.source.id)
      }
    }
  } catch (error) {
    console.log('添加数据源失败', error)
    alert(error?.message || '添加数据源失败')
  }
}

/**
 * 编辑数据源
 */
async function editSource() {
  // 验证表单
  if (!editForm.name.trim()) {
    alert('请输入数据源名称')
    return
  }

  if (editForm.type === '内置OpenList' && !editForm.driver) {
    alert('请选择存储驱动')
    return
  }

  if ((editForm.type === 'WebDAV' || editForm.type === '内置OpenList' || editForm.type === '本地存储') && !editForm.driver && selectedPaths.value.length === 0) {
    alert('请选择挂载目录')
    return
  }

  try {
    // 构建请求参数
    const editData = {
      name: editForm.name.trim(),
      type: apiSourceType(editForm.type)
    }

    if (editForm.type === '内置OpenList') {
      editData.driver = editForm.driver
      editData.driver_type = editForm.driver_type || editForm.driver
      editData.cookie = (editForm.cookie || '').trim()
      editData.mount_path = editForm.mountPath || defaultOpenListMountPath(editForm.driver)
      editData.selected_paths = selectedPaths.value
      Object.assign(editData, collectOpenListFields(editForm))
    } else if (editForm.type === 'WebDAV') {
      const port = editForm.port ? `:${editForm.port}` : ''
      const firstPath = selectedPaths.value[0] || ''
      const cleanFirstPath = firstPath.replace(/^\/+/, '')
      const mainPath = cleanFirstPath ? '/' + cleanFirstPath.split('/').map(encodeURIComponent).join('/') : ''
      
      editData.host = editForm.host.trim()
      editData.port = editForm.port || ''
      editData.protocol = editForm.protocol
      editData.username = editForm.username || ''
      // 空密码表示“保持原密码”，不能覆盖掉后端已保存的凭据。
      if (editForm.password) {
        editData.password = editForm.password
      }
      editData.path = `${editForm.protocol}://${editForm.host}${port}${mainPath}`
      editData.selected_paths = selectedPaths.value
    } else {
      // 本地存储类型类型
      editData.path = selectedPaths.value.join(',')
      editData.selected_paths = selectedPaths.value
    }

    await apiUpdateSource(editingSourceId.value, editData)
    await loadSources()
    showEditModal.value = false
    if (editingSourceId.value) {
      await handleRescan(editingSourceId.value)
    }
  } catch (error) {
    console.log('编辑数据源失败', error)
    alert(error?.message || '编辑数据源失败')
  }
}

/**
 * 删除数据源
 * @param {string} id - 数据源ID
 */
async function handleDelete(id) {
  if (!confirm('确定要删除这个数据源吗？')) return

  try {
    const result = await apiDeleteSource(id)
    
    // 判断数据源删除是否成功
    if (result && result.deleted === true) {
      // 检查 OpenList 挂载是否同步删除成功
      if (result.openlist) {
        if (result.openlist.deleted === true) {
          alert('数据源已删除，OpenList 挂载同步删除成功')
        } else {
          alert('数据源已删除，但 OpenList 挂载删除失败：' + (result.openlist.message || '未知错误'))
        }
      } else {
        alert('数据源已删除')
      }
    } else {
      alert('删除数据源失败')
    }
    
    await loadSources()
  } catch (error) {
    alert('删除数据源失败：' + error.message)
  }
  openedMenu.value = ''
}

/**
 * 格式化扫描状态消息
 * @param {Object} status - 扫描状态对象
 * @returns {string} 格式化后的中文提示文案
 */
function formatScanMessage(status) {
  if (!status) return '正在扫描...';

  if (status.stage === 'scan') {
    return status.current
      ? `正在扫描目录 ${status.current}`
      : '正在扫描目录';
  }

  if (status.stage === 'parse') {
    return status.current
      ? `扫描到电影 ${status.current}`
      : '正在识别影片';
  }

  if (status.stage === 'scrape') {
    return status.current
      ? `正在刮削影视 ${status.current}`
      : '正在刮削影片信息';
  }

  if (status.stage === 'done') {
    return '扫描完成';
  }

  if (status.stage === 'error') {
    return status.error || '扫描失败';
  }

  if (status.stage === 'cancelled') {
    return '扫描已取消';
  }

  return '正在扫描...';
}
async function handleRescan(id) {
  // 发重扫
  try {
    await apiRescanSource(id)
  } catch (error) {
    // 演示模式，模拟扫描过程
    showScanToast(id, '正在连接...', 'scanning', { progress: 0, processedFiles: 0, totalFiles: 100 })
    await new Promise(r => setTimeout(r, 800))
    
    for (let i = 0; i <= 50; i += 5) {
      showScanToast(id, '正在扫描文件...', 'scanning', {
        progress: i, 
        processedFiles: i, 
        totalFiles: 100,
        currentFile: `scanning/file_${i}.mkv`
      })
      await new Promise(r => setTimeout(r, 100))
    }
    
    for (let i = 50; i <= 80; i += 3) {
      showScanToast(id, '正在匹配元数据?..', 'scanning', { 
        progress: i, 
        processedFiles: i, 
        totalFiles: 100,
        currentFile: `matching/title_${i}.json`
      })
      await new Promise(r => setTimeout(r, 120))
    }
    
    for (let i = 80; i <= 100; i += 4) {
      showScanToast(id, '正在生成封面...', 'scanning', { 
        progress: i, 
        processedFiles: i, 
        totalFiles: 100,
        currentFile: `covers/${i}.webp`
      })
      await new Promise(r => setTimeout(r, 80))
    }
    
    showScanToast(id, '扫描完成', 'done', { progress: 100, processedFiles: 100, totalFiles: 100 })
    await new Promise(r => setTimeout(r, 2000))
    hideScanToast()
    openedMenu.value = ''
    await loadSources()
    return
  }
  openedMenu.value = ''

  // 轮询扫描进度，1秒一次
  let message = '正在连接...'
  let scanStatus = 'scanning'
  showScanToast(id, message, 'scanning', { progress: 0 })

  while (scanStatus === 'scanning') {
    await new Promise(r => setTimeout(r, 1000))
    try {
      // 用户已点击取消，停止轮询，避免后端 scanning 状态覆盖前端 cancelled 状态
      if (scanToast.status === 'cancelled') {
        scanStatus = 'cancelled'
        break
      }

      const status = await getScanStatus(id)

      if (status.stage === 'cancelled') {
        scanStatus = 'cancelled'
        message = formatScanMessage(status)
        const processed = status.processed || 0
        const total = status.total || 100
        const progress = total > 0 ? Math.round((processed / total) * 100) : 0
        showScanToast(id, message, 'cancelled', {
          progress,
          processedFiles: processed,
          totalFiles: total,
          currentFile: status.current || ''
        })
        break
      }

      scanStatus = status.scanning ? 'scanning' : 'done'
      message = formatScanMessage(status)

      // 计算进度
      const processed = status.processed || 0
      const total = status.total || 100
      const progress = total > 0 ? Math.round((processed / total) * 100) : 0

      showScanToast(id, message, scanStatus, {
        progress,
        processedFiles: processed,
        totalFiles: total,
        currentFile: status.current || ''
      })
    } catch (error) {
      scanStatus = 'done'
    }
  }

  // 扫描完成或取消后，停留2秒后隐藏并刷新列表
  if (scanStatus !== 'cancelled') {
    hideScanToast()
  }
  await loadSources()
}

/**
 * 浏览目录
 * @param {string} path - 目录路径
 */
async function browseDirectory(path = '/') {
  // 判断当前是添加弹窗还是编辑弹窗
  const form = showEditModal.value ? editForm : sourceForm
  const isOpenListForm = form.type === '内置OpenList'
  const browsePath = isOpenListForm && path === '/' ? defaultOpenListMountPath(form.driver) : path

  if (form.type === 'WebDAV' && !form.host.trim()) {
    alert('请先输入主机地址')
    return
  }

  // 内置OpenList需要选择驱动
  if (form.type === '内置OpenList' && !form.driver.trim()) {
    alert('请先选择存储驱动')
    return
  }

  browsing.value = true
  currentPath.value = browsePath

  try {
    const browseData = {
      type: apiSourceType(form.type),
      host: form.host.trim(),
      port: form.port || '',
      protocol: form.protocol,
      username: form.username || '',
      password: form.password || '',
      path: browsePath,
      driver: form.driver || '',
      driver_type: form.driver_type || form.driver || '',
      cookie: (form.cookie || '').trim()
    }
    if (showEditModal.value && form.type === 'WebDAV' && editingSourceId.value) {
      browseData.source_id = editingSourceId.value
    }
    Object.assign(browseData, collectOpenListFields(form))
    const result = await apiBrowseDirectory(browseData)

    currentPath.value = result.path || browsePath
    browseItems.value = (result.items || []).map(item => ({
      ...item,
      path: decodeURIComponent(item.path || ''),
      name: decodeURIComponent(item.name || ''),
      isDir: !!item.isDir
    }))
    showBrowseModal.value = true
  } catch (error) {
    console.log('浏览目录失败:', error)
    browseItems.value = []
    alert(error?.message || '目录浏览失败')
  } finally {
    browsing.value = false
  }
}

/**
 * 返回上级目录
 */
function goBack() {
  if (currentPath.value === '/') return
  const parts = currentPath.value.split('/')
  parts.pop()
  browseDirectory(parts.join('/') || '/')
}

/**
 * 切换选择
 * @param {Object} item - 目录项
 */
function toggleSelect(item) {
  if (!item.isDir) return
  const index = selectedPaths.value.indexOf(item.path)
  if (index > -1) {
    selectedPaths.value.splice(index, 1)
  } else {
    selectedPaths.value.push(item.path)
  }
}

/**
 * 选择路径
 * @param {string} path - 路径
 */
function selectPath(path) {
  if (!selectedPaths.value.includes(path)) {
    selectedPaths.value.push(path)
  }
  showBrowseModal.value = false
}

/**
 * 确认选择
 */
function confirmSelection() {
  showBrowseModal.value = false
}

/**
 * 清空选择
 */
function clearSelection() {
  selectedPaths.value = []
}

/**
 * 从已选路径移除
 * @param {number} index - 索引
 */
async function removeFromSelectedPaths(index) {
  selectedPaths.value.splice(index, 1)
  
  // 如果正在编辑模式，自动保存到后端
  if (editingSourceId.value && showEditModal.value) {
    try {
      const editData = {
        name: editForm.name.trim(),
        type: apiSourceType(editForm.type),
        selected_paths: selectedPaths.value
      }
      
      if (editForm.type === '内置OpenList') {
        editData.driver = editForm.driver
        editData.driver_type = editForm.driver_type || editForm.driver
        editData.cookie = (editForm.cookie || '').trim()
        editData.mount_path = editForm.mountPath || defaultOpenListMountPath(editForm.driver)
        Object.assign(editData, collectOpenListFields(editForm))
      } else if (editForm.type === 'WebDAV') {
        const port = editForm.port ? `:${editForm.port}` : ''
        const firstPath = selectedPaths.value[0] || ''
        const cleanFirstPath = firstPath.replace(/^\/+/, '')
        const mainPath = cleanFirstPath ? '/' + cleanFirstPath.split('/').map(encodeURIComponent).join('/') : ''
        
        editData.host = editForm.host.trim()
        editData.port = editForm.port || ''
        editData.protocol = editForm.protocol
        editData.username = editForm.username || ''
        editData.password = editForm.password || ''
        editData.path = `${editForm.protocol}://${editForm.host}${port}${mainPath}`
      } else {
        editData.path = selectedPaths.value.join(',')
      }
      
      await apiUpdateSource(editingSourceId.value, editData)
      await loadSources()
    } catch (error) {
      console.log('删除目录时保存失败', error)
    }
  }
}

/**
 * 打开编辑弹窗
 * @param {Object} source - 数据源
 */
function openEditModal(source) {
  editingSourceId.value = source.id
  editForm.name = source.name
  editForm.host = ''
  editForm.port = ''
  editForm.protocol = 'http'
  editForm.username = source.username || ''
  editForm.password = source.password || ''
  editForm.driver = ''
  editForm.cookie = source.cookie || ''
  editForm.mountPath = ''
  editForm.path = ''
  selectedPaths.value = []

  // 统一类型格式，处理后端可能返回的大小写问题
  const normalizedType = normalizeSourceType(source.type)
  editForm.type = normalizedType

  if (normalizedType === 'WebDAV') {
    // 优先使用竖排文字
    if (source.host) {
      editForm.host = source.host
      editForm.port = source.port || ''
      editForm.protocol = source.protocol || 'https'
    } else if (source.path) {
      try {
        const url = new URL(source.path)
        editForm.host = url.hostname
        editForm.port = url.port
        editForm.protocol = url.protocol.replace(':', '')
      } catch {
        editForm.host = ''
      }
    }
    
    // 解析挂载路径
    let mountPathStr = source.mountPath || ''
    if (!mountPathStr && source.path) {
      try {
        const url = new URL(source.path)
        mountPathStr = decodeURIComponent(url.pathname || '/').replace(/^\//, '')
      } catch {
        mountPathStr = ''
      }
    }
    selectedPaths.value = mountPathStr.split(',').filter(p => p.trim())
  } else if (normalizedType === '内置OpenList') {
    // OpenList 类型类型
    editForm.driver = source.driver || ''
    editForm.cookie = source.cookie || ''
    selectedPaths.value = Array.isArray(source.selected_paths) ? [...source.selected_paths] : []
  } else if (normalizedType === '本地存储') {
    // 本地存储类型类型
    selectedPaths.value = Array.isArray(source.selected_paths) ? [...source.selected_paths] : []
  } else {
    // 未知类型，尝试通用处理
    selectedPaths.value = Array.isArray(source.selected_paths) ? [...source.selected_paths] : []
  }

  showEditModal.value = true
  openedMenu.value = ''
}

/**
 * 统一数据源类型格式? * 处理后端可能返回的不同类型值? */
function normalizeSourceType(type) {
  if (!type) return ''
  const lower = type.toLowerCase()
  if (lower.includes('webdav')) return 'WebDAV'
  if (lower.includes('openlist')) return '内置OpenList'
  if (lower.includes('local') || lower.includes('本地')) return '本地存储'
  return type
}

// 监听 OpenList 驱动变化
watch(() => sourceForm.driver, (newDriver) => {
  if (newDriver === 'quark') {
    sourceForm.mountPath = '/quark'
  } else if (newDriver === 'baidu') {
    sourceForm.mountPath = '/baidu'
  }
})
</script>

<style scoped>
/* ==================== 页面核心样式 ==================== */
.server-page {
  width: 100%;
  min-height: 100vh;
  padding: 34px;
  box-sizing: border-box;
  color: #f7f9ff;
  background: #1b1b1c;
}

/* ==================== 响应式样式 ==================== */
@media (max-width: 768px) {
  .server-page {
    padding: 20px;
  }
}

/* 扫描进度弹窗样式已迁移至components/common/ScanToast.vue */
</style>
