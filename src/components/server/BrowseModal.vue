/**
 * 目录浏览弹窗组件
 *
 * 功能：
 * 1. 浏览目录结构
 * 2. 单选/多选目录（支持全选/反选）
 * 3. 确认选择
 * 4. 可拖动的小卡片样式
 * 5. 显示已选目录数量和预览
 */
<template>
  <n-modal
    v-model:show="isShow"
    preset="card"
    class="browse-modal-card"
    :style="modalStyle"
    :mask-closable="false"
  >
    <!-- 拖动头部 -->
    <div 
      class="drag-header"
      @mousedown="startDrag"
    >
      <span class="drag-title">选择目录</span>
      <button class="drag-close" @click="isShow = false">×</button>
    </div>
    
    <div class="browse-modal">
      <!-- 头部 -->
      <div class="browse-header">
        <!-- 返回按钮 -->
        <button
          class="back-btn"
          @click="$emit('goBack')"
          :disabled="currentPath === '/'"
        >
          返回
        </button>

        <!-- 当前路径 -->
        <span class="current-path">{{ currentPath }}</span>

        <!-- 右侧操作 -->
        <div class="header-right">
          <!-- 多选开关 -->
          <label class="multi-select-switch">
            <input 
              type="checkbox" 
              :checked="isMultiSelect" 
              @change="$emit('update:isMultiSelect', $event.target.checked)" 
            />
            <span>多选</span>
          </label>

          <!-- 选择按钮 -->
          <button class="select-dir-btn" @click="handleSelect">
            选择此目录
          </button>
        </div>
      </div>

      <!-- 已选择信息 -->
      <div v-if="isMultiSelect && selectedPaths.length > 0" class="selected-info">
        <span class="selected-count">已选择 {{ selectedPaths.length }} 个目录</span>
        <div class="selected-actions">
          <button class="select-all-btn" @click="handleSelectAll">
            {{ isAllSelected ? '取消全选' : '全选' }}
          </button>
          <button class="clear-btn" @click="$emit('clearSelection')">清空</button>
        </div>
      </div>

      <!-- 目录列表 -->
      <div class="browse-list">
        <!-- 空状态 -->
        <div v-if="items.length === 0" class="browse-empty">
          <div class="empty-icon">📂</div>
          <div class="empty-text">目录为空</div>
        </div>

        <!-- 多选模式：全选复选框行 -->
        <div v-if="isMultiSelect && items.length > 0 && hasDirectories" class="browse-item select-all-row">
          <span class="item-checkbox" @click.stop="handleSelectAll">
            {{ isAllSelected ? '✓' : '' }}
          </span>
          <span class="item-icon">📁</span>
          <span class="item-name">{{ isAllSelected ? '取消全选' : '全选此目录下所有文件夹' }}</span>
        </div>

        <!-- 目录项 -->
        <div
          v-for="item in items"
          :key="item.path"
          class="browse-item"
          :class="{
            'is-dir': item.isDir,
            'is-selected': item.isDir && isSelected(item.path),
            'is-file': !item.isDir
          }"
        >
          <!-- 多选复选框 -->
          <span
            v-if="isMultiSelect && item.isDir"
            class="item-checkbox"
            @click.stop="toggleSelect(item)"
          >
            {{ isSelected(item.path) ? '✓' : '' }}
          </span>

          <!-- 图标 -->
          <span
            class="item-icon"
            @click="handleItemClick(item)"
          >
            {{ item.isDir ? '📁' : '📄' }}
          </span>

          <!-- 名称 -->
          <span
            class="item-name"
            @click="handleItemClick(item)"
          >
            {{ item.name }}
          </span>

          <!-- 进入子目录按钮 -->
          <button
            v-if="isMultiSelect && item.isDir"
            class="add-subdir-btn"
            @click="$emit('browse', item.path)"
            title="进入子目录"
          >
            进入
          </button>

          <!-- 文件大小 -->
          <span v-if="!item.isDir && item.size" class="item-size">
            {{ formatSize(item.size) }}
          </span>
        </div>
      </div>

      <!-- 多选模式底部 -->
      <div v-if="isMultiSelect" class="browse-footer">
        <button
          class="confirm-btn"
          @click="$emit('confirm')"
          :disabled="selectedPaths.length === 0"
        >
          确认选择 ({{ selectedPaths.length }})
        </button>
      </div>
    </div>
  </n-modal>
</template>

<script setup>
/**
 * ==================== Props 定义 ====================
 */
import { computed, ref, watch } from 'vue'

const props = defineProps({
  // 是否显示
  modelValue: {
    type: Boolean,
    default: false
  },
  // 当前路径
  currentPath: {
    type: String,
    default: '/'
  },
  // 目录项列表
  items: {
    type: Array,
    default: () => []
  },
  // 是否多选模式
  isMultiSelect: {
    type: Boolean,
    default: true
  },
  // 已选择的路径列表
  selectedPaths: {
    type: Array,
    default: () => []
  }
})

/**
 * ==================== Emit 定义 ====================
 */
const emit = defineEmits([
  'update:modelValue',
  'update:isMultiSelect',
  'goBack',
  'browse',
  'select',
  'toggleSelect',
  'clearSelection',
  'confirm'
])

/**
 * ==================== 计算属性 ====================
 */
const isShow = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

/**
 * ==================== 拖动功能 ====================
 */

// 弹窗位置
const positionX = ref(0)
const positionY = ref(0)

// 拖动状态
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)

// 弹窗样式（固定大小 + 位置）
const modalStyle = computed(() => ({
  width: '480px',
  maxWidth: '480px',
  position: 'fixed',
  left: `calc(50% + ${positionX.value}px)`,
  top: `calc(50% + ${positionY.value}px)`,
  transform: 'translate(-50%, -50%)'
}))

// 弹窗关闭时重置位置
watch(isShow, (show) => {
  if (!show) {
    positionX.value = 0
    positionY.value = 0
  }
})

/**
 * 开始拖动
 * @param {MouseEvent} e
 */
function startDrag(e) {
  // 避免点击关闭按钮时触发拖动
  if (e.target.closest('.drag-close')) return
  
  isDragging.value = true
  dragStartX.value = e.clientX - positionX.value
  dragStartY.value = e.clientY - positionY.value
  
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

/**
 * 拖动中
 * @param {MouseEvent} e
 */
function onDrag(e) {
  if (!isDragging.value) return
  positionX.value = e.clientX - dragStartX.value
  positionY.value = e.clientY - dragStartY.value
}

/**
 * 结束拖动
 */
function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

/**
 * ==================== 计算属性 ====================
 */

/**
 * 当前目录是否有子目录
 */
const hasDirectories = computed(() => {
  return props.items.some(item => item.isDir)
})

/**
 * 当前目录下的所有子目录是否都已选中
 */
const isAllSelected = computed(() => {
  const directories = props.items.filter(item => item.isDir)
  if (directories.length === 0) return false
  return directories.every(item => props.selectedPaths.includes(item.path))
})

/**
 * ==================== 方法 ====================
 */

/**
 * 检查路径是否已选择
 * @param {string} path - 路径
 * @returns {boolean}
 */
function isSelected(path) {
  return props.selectedPaths.includes(path)
}

/**
 * 全选/取消全选当前目录下的所有子目录
 */
function handleSelectAll() {
  const directories = props.items.filter(item => item.isDir)
  if (isAllSelected.value) {
    // 取消全选
    directories.forEach(dir => {
      if (props.selectedPaths.includes(dir.path)) {
        emit('toggleSelect', dir)
      }
    })
  } else {
    // 全选
    directories.forEach(dir => {
      if (!props.selectedPaths.includes(dir.path)) {
        emit('toggleSelect', dir)
      }
    })
  }
}

/**
 * 处理目录项点击
 * 点击目录名称/图标始终进入子目录（无论单选还是多选模式）
 * 选择状态通过复选框来切换
 * @param {Object} item - 目录项
 */
function handleItemClick(item) {
  if (!item.isDir) return
  
  // 点击目录名称/图标始终进入子目录
  emit('browse', item.path)
}

/**
 * 切换选择
 * @param {Object} item - 目录项
 */
function toggleSelect(item) {
  emit('toggleSelect', item)
}

/**
 * 选择当前目录
 */
function handleSelect() {
  emit('select', props.currentPath)
  if (!props.isMultiSelect) {
    isShow.value = false
  }
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string}
 */
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
}
</script>

<style scoped>
/* ==================== 弹窗样式 ==================== */
.browse-modal-card {
  width: 480px !important;
  max-width: 480px !important;
}

/* 拖动头部 */
.drag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  margin-bottom: 12px;
  cursor: move;
  user-select: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.drag-title {
  font-size: 16px;
  font-weight: 500;
}

.drag-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  color: #9ca8ba;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.drag-close:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #f6f8ff;
}

.browse-modal {
  display: flex;
  flex-direction: column;
  max-height: 50vh;
}

/* ==================== 头部样式 ==================== */
.browse-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.back-btn {
  padding: 8px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: transparent;
  color: #9ca8ba;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.back-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: #f6f8ff;
}

.back-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.current-path {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: #f6f8ff;
  font-size: 13px;
  font-family: monospace;
  word-break: break-all;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 多选开关 */
.multi-select-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #9ca8ba;
  font-size: 13px;
  cursor: pointer;
}

.multi-select-switch input {
  width: 16px;
  height: 16px;
  accent-color: #69f0c6;
}

.select-dir-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
  color: #06121a;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.select-dir-btn:hover {
  opacity: 0.9;
}

/* ==================== 已选择信息样式 ==================== */
.selected-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  margin-bottom: 12px;
  border-radius: 8px;
  background: rgba(105, 240, 198, 0.08);
  border: 1px solid rgba(105, 240, 198, 0.15);
}

.selected-count {
  color: #69f0c6;
  font-size: 13px;
}

.selected-actions {
  display: flex;
  gap: 8px;
}

.select-all-btn {
  padding: 4px 12px;
  border: 1px solid rgba(105, 240, 198, 0.3);
  border-radius: 6px;
  background: rgba(105, 240, 198, 0.1);
  color: #69f0c6;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.select-all-btn:hover {
  background: rgba(105, 240, 198, 0.18);
}

.clear-btn {
  padding: 4px 12px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.clear-btn:hover {
  background: rgba(239, 68, 68, 0.18);
}

/* ==================== 目录列表样式 ==================== */
.browse-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.browse-empty {
  padding: 40px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  color: #6b7280;
  font-size: 14px;
}

/* 全选行样式 */
.select-all-row {
  background: rgba(105, 240, 198, 0.05);
  border-left: 3px solid #69f0c6;
}

.select-all-row .item-name {
  color: #69f0c6;
  font-weight: 500;
}

.browse-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  transition: background 0.2s ease;
}

.browse-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.browse-item.is-selected {
  background: rgba(105, 240, 198, 0.08);
}

.item-checkbox {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 4px;
  color: #69f0c6;
  font-size: 14px;
  cursor: pointer;
}

.browse-item.is-selected .item-checkbox {
  background: rgba(105, 240, 198, 0.2);
  border-color: #69f0c6;
}

.item-icon {
  font-size: 16px;
  cursor: pointer;
}

.item-name {
  flex: 1;
  color: #f6f8ff;
  font-size: 14px;
  cursor: pointer;
}

.add-subdir-btn {
  padding: 4px 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  background: transparent;
  color: #9ca8ba;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.add-subdir-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f6f8ff;
}

.item-size {
  color: #6b7280;
  font-size: 12px;
}

/* ==================== 底部样式 ==================== */
.browse-footer {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.confirm-btn {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
  color: #06121a;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.confirm-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
