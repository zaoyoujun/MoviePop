﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿/**
 * 娣诲姞鏁版嵁婧愬脊绐楃粍浠? *
 * 鍔熻兘锛? * 1. WebDAV 閰嶇疆琛ㄥ崟
 * 2. OpenList 閰嶇疆琛ㄥ崟
 * 3. 鏈湴瀛樺偍閰嶇疆琛ㄥ崟
 * 4. 鐩綍娴忚鍔熻兘
 * 5. 鍙嫋鍔ㄧ殑灏忓崱鐗囨牱寮? */
<template>
  <n-modal
    v-model:show="isShow"
    preset="card"
    class="source-modal"
    :style="modalStyle"
    :mask-closable="false"
  >
    <!-- 寮圭獥澶撮儴锛堝彲鎷栧姩鍖哄煙锛?-->
    <div 
      class="modal-header" 
      @mousedown="startDrag"
    >
      <h3>{{ modalTitle }}</h3>
      <button class="close-btn" @click="isShow = false">返回</button>
    </div>

    <!-- 寮圭獥鍐呭 -->
    <div class="modal-content">
      <!-- 鍚嶇О -->
      <div class="form-item">
        <label>名称</label>
        <input v-model="formData.name" type="text" placeholder="例如：夸克网盘" />
      </div>

      <!-- ==================== OpenList 閰嶇疆 ==================== -->
      <template v-if="formType === '鍐呯疆OpenList' || formType === '内置OpenList'">
        <!-- 编辑模式：只显示名称和挂载目录 -->
        <template v-if="isEdit">
          <!-- 挂载目录 -->
          <div class="form-item">
            <label>挂载目录</label>
            <div class="mount-paths-container">
              <!-- 鏃犳寕杞界洰褰曟椂 -->
              <div v-if="selectedPaths.length === 0" class="no-paths">
                <span class="no-paths-icon">📁</span>
                <span class="no-paths-text">暂无挂载目录</span>
                <span class="no-paths-hint">点击下方按钮添加网盘目录</span>
              </div>

              <!-- 鎸傝浇鐩綍鍒楄〃 -->
              <div v-else class="mount-paths-grid">
                <div
                  v-for="(path, index) in selectedPaths"
                  :key="index"
                  class="mount-path-card"
                >
                  <span class="path-icon">📁</span>
                  <span class="path-text">{{ path }}</span>
                  <button class="remove-btn" @click.stop.prevent="removePath(index)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </div>
              </div>

              <!-- 娣诲姞鐩綍鎸夐挳 -->
              <button
                class="add-path-btn"
                @click="$emit('browse')"
                :disabled="isBrowsing"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 5v14"></path>
                  <path d="M5 12h14"></path>
                </svg>
                {{ isBrowsing ? '浏览中...' : '添加目录' }}
              </button>
            </div>
          </div>
        </template>

        <!-- 添加模式：显示完整配置 -->
        <template v-else>
          <!-- 瀛樺偍椹卞姩閫夋嫨 -->
          <div class="form-item">
            <label>选择存储驱动</label>
            <div class="driver-options">
              <button
                v-for="driver in driverOptions"
                :key="driver.value"
                type="button"
                class="driver-option"
                :class="{ active: formData.driver === driver.value }"
                :disabled="driver.disabled"
                @click.stop.prevent="selectDriver(driver)"
              >
                <span class="driver-icon">{{ formatDriverIcon(driver.icon) }}</span>
                <span class="driver-name">{{ driver.label }}</span>
              </button>
            </div>
          </div>

          <!-- Cookie 杈撳叆 -->
          <template v-if="formDriver">
            <div
              v-for="field in currentDriverFields"
              :key="field.key"
              class="form-item"
            >
              <div class="label-row">
                <label>{{ field.label || field.key }}</label>
                <button 
                  v-if="field.key === 'cookie'"
                  type="button"
                  class="paste-btn" 
                  @click="pasteCookie"
                  title="从剪贴板粘贴"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                  </svg>
                </button>
              </div>
              <textarea
                v-if="field.type === 'textarea'"
                v-model="formData[field.key]"
                :placeholder="field.placeholder || driverPlaceholder.cookie"
                class="cookie-input"
                rows="3"
              ></textarea>
              <input
                v-else
                v-model="formData[field.key]"
                :type="field.type === 'password' ? 'password' : 'text'"
                :placeholder="field.placeholder || ''"
                class="cookie-input"
              />
              <div v-if="field.help || field.key === 'cookie'" class="cookie-hint">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path d="M12 16v-4"></path>
                  <path d="M12 8h.01"></path>
                </svg>
                <span>{{ field.help || driverHint }}</span>
              </div>
            </div>

            <!-- 鎸傝浇鐩綍 -->
            <div class="form-item">
              <label>挂载目录</label>
              <div class="mount-paths-container">
                <!-- 鏃犳寕杞界洰褰曟椂 -->
                <div v-if="selectedPaths.length === 0" class="no-paths">
                  <span class="no-paths-icon">📁</span>
                  <span class="no-paths-text">暂无挂载目录</span>
                  <span class="no-paths-hint">点击下方按钮添加网盘目录</span>
                </div>

                <!-- 鎸傝浇鐩綍鍒楄〃 -->
                <div v-else class="mount-paths-grid">
                  <div
                    v-for="(path, index) in selectedPaths"
                    :key="index"
                    class="mount-path-card"
                  >
                    <span class="path-icon">📁</span>
                    <span class="path-text">{{ path }}</span>
                    <button class="remove-btn" @click="removePath(index)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                </div>

                <!-- 娣诲姞鐩綍鎸夐挳 -->
                <button
                  class="add-path-btn"
                  @click="$emit('browse')"
                  :disabled="isBrowsing"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 5v14"></path>
                    <path d="M5 12h14"></path>
                  </svg>
                  {{ isBrowsing ? '浏览中...' : '添加目录' }}
                </button>
              </div>
            </div>
          </template>
        </template>
      </template>

      <!-- ==================== WebDAV 閰嶇疆 ==================== -->
      <template v-else-if="formType === 'WebDAV'">
        <div class="form-item-row">
          <div class="form-item flex-1">
            <label>主机</label>
            <input v-model="formData.host" type="text" placeholder="dav.example.com" />
          </div>
          <div class="form-item port-item">
            <label>端口</label>
            <input v-model="formData.port" type="text" placeholder="选填" />
          </div>
        </div>

        <div class="form-item">
          <label>协议</label>
          <div class="protocol-buttons">
            <button
              class="protocol-btn"
              :class="{ active: formData.protocol === 'http' }"
              @click="formData.protocol = 'http'"
            >
              HTTP
            </button>
            <button
              class="protocol-btn"
              :class="{ active: formData.protocol === 'https' }"
              @click="formData.protocol = 'https'"
            >
              HTTPS
            </button>
          </div>
        </div>

        <div class="form-item">
          <label>用户名</label>
          <input v-model="formData.username" type="text" placeholder="选填" />
        </div>

        <div class="form-item">
          <label>密码</label>
          <input v-model="formData.password" type="password" placeholder="选填" />
        </div>

        <div class="form-item">
          <label>挂载目录</label>
          <div class="mount-paths-container">
            <!-- 鏃犳寕杞界洰褰曟椂 -->
            <div v-if="selectedPaths.length === 0" class="no-paths">
              <span class="no-paths-text">暂无挂载目录</span>
            </div>

            <!-- 鎸傝浇鐩綍鍒楄〃 -->
            <div v-else class="mount-paths-grid">
              <div
                v-for="(path, index) in selectedPaths"
                :key="index"
                class="mount-path-card"
              >
                <span class="path-icon">📁</span>
                <span class="path-text">{{ path }}</span>
                <button class="remove-btn" @click="removePath(index)">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 娣诲姞鐩綍鎸夐挳 -->
            <button
              class="add-path-btn"
              @click="$emit('browse')"
              :disabled="isBrowsing"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 5v14"></path>
                <path d="M5 12h14"></path>
              </svg>
              {{ isBrowsing ? '浏览中...' : '添加目录' }}
            </button>
          </div>
        </div>
      </template>

      <!-- ==================== 鏈湴瀛樺偍閰嶇疆 ==================== -->
      <template v-else-if="formType === '鏈湴瀛樺偍' || formType === '本地存储'">
        <div class="form-item">
          <label>挂载目录</label>
          <div class="mount-paths-container">
            <!-- 鏃犳寕杞界洰褰曟椂 -->
            <div v-if="selectedPaths.length === 0" class="no-paths">
              <span class="no-paths-text">暂无挂载目录</span>
            </div>

            <!-- 鎸傝浇鐩綍鍒楄〃 -->
            <div v-else class="mount-paths-grid">
              <div
                v-for="(path, index) in selectedPaths"
                :key="index"
                class="mount-path-card"
              >
                <span class="path-icon">📁</span>
                <span class="path-text">{{ path }}</span>
                <button class="remove-btn" @click="removePath(index)">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 娣诲姞鐩綍鎸夐挳 -->
            <button
              class="add-path-btn"
              @click="$emit('browse')"
              :disabled="isBrowsing"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 5v14"></path>
                <path d="M5 12h14"></path>
              </svg>
              {{ isBrowsing ? '浏览中...' : '添加目录' }}
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- 寮圭獥搴曢儴 -->
    <div class="modal-footer">
      <button class="verify-btn" @click="$emit('verify')" :disabled="verifying">
        {{ verifying ? '验证中...' : '测试连接' }}
      </button>
      <button class="connect-btn" @click="$emit('submit')">添加</button>
      <button class="cancel-btn" @click="isShow = false">取消</button>
    </div>
  </n-modal>
</template>

<script setup>
/**
 * ==================== Props 瀹氫箟 ====================
 */
import { computed, ref, watch, toRef, toRefs, onMounted } from 'vue'

// API 鍑芥暟
import { getOpenListDrivers } from '@/api/openlist'

const props = defineProps({
  verifying: { type: Boolean, default: false },
  // 鏄惁鏄剧ず
  modelValue: {
    type: Boolean,
    default: false
  },
  // 琛ㄥ崟鏁版嵁
  formData: {
    type: Object,
    required: true
  },
  // 鎸傝浇鐩綍鍒楄〃
  selectedPaths: {
    type: Array,
    default: () => []
  },
  // 鏄惁姝ｅ湪娴忚
  isBrowsing: {
    type: Boolean,
    default: false
  },
  // 鏄惁鏄紪杈戞ā寮?
  isEdit: {
    type: Boolean,
    default: false
  }
})

/**
 * ==================== Emit 瀹氫箟 ====================
 */
const emit = defineEmits([
  'update:modelValue',
  'verify',
  'submit',
  'browse',
  'removePath'
])

/**
 * ==================== 璁＄畻灞炴€?====================
 */
const isShow = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 浣跨敤 toRefs 纭繚 formData 鐨勫搷搴斿紡
const { formData } = toRefs(props)

// 纭繚 formData.type 鐨勫搷搴斿紡杩借釜
const formType = computed(() => props.formData?.type || '')
const formDriver = computed(() => props.formData?.driver || '')

const modalTitle = computed(() => {
  if (props.isEdit) {
    return '编辑数据源'
  }
  if (props.formData.type === '鍐呯疆OpenList' || props.formData.type === '内置OpenList') {
    return '添加内置OpenList'
  }
  return `添加 ${props.formData.type}`
})

// 椹卞姩閫夐」鍒楄〃锛堜粠API鍔ㄦ€佸姞杞斤級
const driverOptions = ref([
  { value: 'quark', driver: 'Quark', label: '夸克网盘', icon: 'folder', fields: defaultDriverFields('quark') },
  { value: 'aliyun', driver: 'AliyundriveOpen', label: '阿里云盘 Open', icon: 'folder', fields: defaultDriverFields('aliyun') },
  { value: '115', driver: '115 Cloud', label: '115 网盘', icon: 'folder', fields: defaultDriverFields('115') },
  { value: 'baidu', driver: 'BaiduNetdisk', label: '百度网盘', icon: 'folder', fields: defaultDriverFields('baidu') },
  { value: 'webdav', driver: 'WebDav', label: 'WebDAV', icon: 'folder', fields: defaultDriverFields('webdav') }
])

/**
 * 鍔犺浇 OpenList 椹卞姩鍒楄〃
 */
async function loadDrivers() {
  try {
    const drivers = await getOpenListDrivers()
    if (Array.isArray(drivers)) {
      driverOptions.value = drivers.map(normalizeDriverOption).filter(driver => driver.value)
    }
  } catch (error) {
    console.log('加载驱动列表失败，使用默认值', error)
  }
}

function normalizeDriverOption(driver) {
  const canonicalDriver = driver.driver || driver.value || driver.name || ''
  const value = driver.value || driver.name || driverAlias(canonicalDriver)
  return {
    ...driver,
    driver: canonicalDriver,
    value,
    label: driver.label || canonicalDriver || value,
    icon: driver.icon || 'folder',
    disabled: Boolean(driver.disabled),
    fields: Array.isArray(driver.fields) ? driver.fields : defaultDriverFields(value)
  }
}

function driverAlias(driver) {
  const key = String(driver || '').toLowerCase()
  const aliases = {
    quark: 'quark',
    aliyundriveopen: 'aliyun',
    '115 cloud': '115',
    baidunetdisk: 'baidu',
    webdav: 'webdav'
  }
  return aliases[key] || key
}

function formatDriverIcon(icon) {
  return icon === 'folder' || !icon ? '📁' : icon
}

function defaultDriverFields(value) {
  if (value === 'aliyun') {
    return [
      { key: 'refresh_token', label: 'Refresh Token', required: true },
      { key: 'root_folder_id', label: '根目录文件 ID', placeholder: 'root' },
      { key: 'drive_type', label: '云盘类型', placeholder: 'default' }
    ]
  }
  if (value === 'baidu') {
    return [
      { key: 'refresh_token', label: 'Refresh Token', required: true },
      { key: 'root_folder_path', label: '根目录路径', placeholder: '/' }
    ]
  }
  if (value === 'webdav') {
    return [
      { key: 'address', label: '地址', required: true, placeholder: 'http://example.com/dav' },
      { key: 'username', label: '用户名' },
      { key: 'password', label: '密码', type: 'password' },
      { key: 'root_folder_path', label: '根目录路径', placeholder: '/' }
    ]
  }
  return [
    { key: 'cookie', label: 'Cookie', type: 'textarea', required: true },
    { key: 'root_folder_id', label: '根目录 ID', placeholder: '0' }
  ]
}

const currentDriver = computed(() => {
  return driverOptions.value.find(driver => driver.value === props.formData.driver) || null
})

const currentDriverFields = computed(() => {
  const fields = currentDriver.value?.fields || defaultDriverFields(props.formData.driver)
  return fields.filter(field => field.type !== 'hidden')
})

function selectDriver(driver) {
  if (!driver || driver.disabled) return
  const fields = driver.fields || defaultDriverFields(driver.value)
  props.formData.driver = driver.value
  props.formData.driver_type = driver.driver || driver.value
  for (const field of fields) {
    if (props.formData[field.key] === undefined) {
      props.formData[field.key] = field.placeholder && !field.placeholder.startsWith('http') ? field.placeholder : ''
    }
  }
}

// Load OpenList drivers when the modal component is mounted.
onMounted(() => {
  loadDrivers()
})

const driverPlaceholder = computed(() => {
  if (props.formData.driver === 'quark') {
    return {
      cookie: '请输入夸克网盘 Cookie',
      mountPath: '/quark'
    }
  }
  return {
    cookie: '请输入网盘 Cookie',
    mountPath: '/baidu'
  }
})

const driverHint = computed(() => {
  if (props.formData.driver === 'quark') {
    return '请在夸克网盘网页登录后，从浏览器开发者工具复制 Cookie'
  }
  return '请填写当前驱动需要的登录信息'
})

/**
 * 浠庡壀璐存澘绮樿创Cookie
 */
async function pasteCookie() {
  try {
    const text = await navigator.clipboard.readText()
    if (text) {
      props.formData.cookie = text
    }
  } catch (err) {
    console.log('粘贴失败:', err)
  }
}

/**
 * ==================== 鎷栧姩鍔熻兘 ====================
 */

// 寮圭獥浣嶇疆
const positionX = ref(0)
const positionY = ref(0)

// Dragging state.
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)

// Modal size and position.
const modalStyle = computed(() => ({
  width: '480px',
  maxWidth: '480px',
  position: 'fixed',
  left: `calc(50% + ${positionX.value}px)`,
  top: `calc(50% + ${positionY.value}px)`,
  transform: 'translate(-50%, -50%)'
}))

// Reset position after closing.
watch(isShow, (show) => {
  if (!show) {
    positionX.value = 0
    positionY.value = 0
  }
})

/**
 * 寮€濮嬫嫋鍔? * @param {MouseEvent} e
 */
function startDrag(e) {
  // 閬垮厤鐐瑰嚮鎸夐挳鏃惰Е鍙戞嫋鍔?  if (e.target.closest('.close-btn')) return
  
  isDragging.value = true
  dragStartX.value = e.clientX - positionX.value
  dragStartY.value = e.clientY - positionY.value
  
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

/**
 * 鎷栧姩涓? * @param {MouseEvent} e
 */
function onDrag(e) {
  if (!isDragging.value) return
  positionX.value = e.clientX - dragStartX.value
  positionY.value = e.clientY - dragStartY.value
}

/**
 * 缁撴潫鎷栧姩
 */
function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

/**
 * ==================== 鏂规硶 ====================
 */

/**
 * 绉婚櫎鎸傝浇鐩綍
 * @param {number} index - 鐩綍绱㈠紩
 */
function removePath(index) {
  emit('removePath', index)
}
</script>

<style scoped>
/* ==================== 寮圭獥鏍峰紡 ==================== */
.source-modal {
  width: 480px !important;
  max-width: 480px !important;
}

/* 澶撮儴锛堝彲鎷栧姩鍖哄煙锛?*/
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  cursor: move;
  user-select: none;
  padding: 8px 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  padding: 6px 14px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: transparent;
  color: #9ca8ba;
  cursor: pointer;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f6f8ff;
}

/* ==================== 表单样式 ==================== */
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 50vh;
  overflow-y: auto;
  padding-right: 4px;
}

.modal-content::-webkit-scrollbar {
  width: 6px;
}

.modal-content::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.04);
  border-radius: 3px;
}

.modal-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.modal-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-item label {
  color: #9ca8ba;
  font-size: 13px;
}

.form-item input,
.form-item textarea,
.driver-select {
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: #f6f8ff;
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.form-item input:focus,
.form-item textarea:focus,
.driver-select:focus {
  outline: none;
  border-color: #69f0c6;
}

.form-item input::placeholder,
.form-item textarea::placeholder {
  color: #6b7280;
}

.form-item textarea {
  min-height: 88px;
  resize: vertical;
}

/* 鏍囩琛岋紙甯﹂澶栨寜閽級 */
.label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.paste-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: #9ca8ba;
  cursor: pointer;
  transition: all 0.2s ease;
}

.paste-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f6f8ff;
}

/* Cookie 杈撳叆妗?*/
.cookie-input {
  font-family: monospace;
}

/* Cookie 鎻愮ず */
.cookie-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(105, 240, 198, 0.06);
  color: #9ca8ba;
  font-size: 12px;
}

/* 椹卞姩閫夐」 */
.driver-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.driver-option {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: #9ca8ba;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.driver-option:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
}

.driver-option.active {
  background: rgba(105, 240, 198, 0.12);
  border-color: #69f0c6;
  color: #69f0c6;
}

.driver-option:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.driver-icon {
  font-size: 18px;
}

/* 琛ㄥ崟椤硅 */
.form-item-row {
  display: flex;
  gap: 12px;
}

.port-item {
  flex: 0 0 100px;
}

/* 鍗忚閫夋嫨鎸夐挳 */
.protocol-buttons {
  display: flex;
  gap: 8px;
}

.protocol-btn {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: transparent;
  color: #9ca8ba;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.protocol-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.protocol-btn.active {
  background: rgba(105, 240, 198, 0.12);
  border-color: #69f0c6;
  color: #69f0c6;
}

/* ==================== 鎸傝浇鐩綍鏍峰紡 ==================== */
.mount-paths-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.no-paths {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 10px;
}

.no-paths-icon {
  font-size: 32px;
  opacity: 0.5;
}

.no-paths-text {
  color: #f6f8ff;
  font-size: 14px;
}

.no-paths-hint {
  color: #6b7280;
  font-size: 12px;
}

.mount-paths-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mount-path-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
}

.path-icon {
  font-size: 16px;
}

.path-text {
  flex: 1;
  color: #f6f8ff;
  font-size: 13px;
  word-break: break-all;
}

.remove-btn {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #9ca8ba;
  cursor: pointer;
  transition: all 0.2s ease;
}

.remove-btn:hover {
  background: rgba(255, 107, 107, 0.12);
  color: #ff6b6b;
}

.add-path-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.24);
  border-radius: 10px;
  background: transparent;
  color: #9ca8ba;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.add-path-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.4);
  color: #f6f8ff;
}

.add-path-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==================== 搴曢儴鎸夐挳鏍峰紡 ==================== */
.modal-footer {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.connect-btn,
.cancel-btn {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.connect-btn {
  border: none;
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
  color: #06121a;
}

.connect-btn:hover {
  opacity: 0.9;
}

.cancel-btn {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: transparent;
  color: #9ca8ba;
}

.verify-btn {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid rgba(105, 240, 198, 0.4);
  background: transparent;
  color: #69f0c6;
  transition: all 0.2s ease;
}
.verify-btn:hover:not(:disabled) {
  background: rgba(105, 240, 198, 0.1);
}
.verify-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f6f8ff;
}
</style>

