/**
 * 服务器页面头部组件
 *
 * 功能：
 * 1. 标题和描述
 * 2. 添加数据源按钮
 * 3. 数据源类型选择器
 */
<template>
  <header class="server-header">
    <!-- 标题区域 -->
    <div>
      <h1>服务器</h1>
      <p>集中管理 WebDAV、OpenList 与本地媒体源，查看每个资源库的匹配情况。</p>
    </div>

    <!-- 操作区域 -->
    <div class="header-actions">
      <!-- 添加数据源按钮 -->
      <n-button
        type="primary"
        size="large"
        class="add-button"
        @click="$emit('toggleTypePicker')"
      >
        <template #icon>
          <n-icon><AddOutline /></n-icon>
        </template>
        添加数据源
      </n-button>

      <!-- 类型选择器 -->
      <div v-if="showTypePicker" class="type-picker">
        <h2>选择服务器类型：</h2>
        <div class="type-options">
          <button
            v-for="option in sourceOptions"
            :key="option.value"
            type="button"
            :disabled="option.disabled"
            :class="{ disabled: option.disabled }"
            @click="$emit('selectType', option)"
          >
            <span v-if="option.badge" class="option-badge">{{ option.badge }}</span>
            {{ option.label }}
            <span v-if="option.disabled" class="disabled-hint">（未启用）</span>
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
/**
 * ==================== 导入 ====================
 */
import { AddOutline } from '@vicons/ionicons5'

/**
 * ==================== 属性定义 ====================
 */
defineProps({
  // 是否显示类型选择器
  showTypePicker: {
    type: Boolean,
    default: false
  },
  // 数据源类型选项
  sourceOptions: {
    type: Array,
    default: () => []
  }
})

/**
 * ==================== 事件定义 ====================
 */
defineEmits(['toggleTypePicker', 'selectType'])
</script>

<style scoped>
/* ==================== 头部容器样式 ==================== */
.server-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 32px;
}

.server-header h1 {
  margin: 0 0 10px;
  font-size: 38px;
}

.server-header p {
  margin: 0;
  color: #9ca8ba;
  max-width: 600px;
}

/* ==================== 操作区域样式 ==================== */
.header-actions {
  position: relative;
}

/* 添加按钮 */
.add-button {
  border-radius: 14px;
}

/* 类型选择器 */
.type-picker {
  position: absolute;
  right: 0;
  top: calc(100% + 12px);
  z-index: 100;
  min-width: 240px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  background: #12121a;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.type-picker h2 {
  margin: 0 0 16px;
  font-size: 14px;
  color: #9ca8ba;
}

.type-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.type-options button {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: #f6f8ff;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.type-options button:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}

/* 禁用状态样式 */
.type-options button.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.05);
}

.type-options button.disabled:hover {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.05);
}

.disabled-hint {
  color: #6b7280;
  font-size: 12px;
}

.option-badge {
  padding: 2px 8px;
  border-radius: 6px;
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
  color: #06121a;
  font-size: 11px;
  font-weight: 600;
}

/* ==================== 响应式样式 ==================== */
@media (max-width: 768px) {
  .server-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .type-picker {
    position: static;
    width: 100%;
    margin-top: 12px;
  }
}
</style>
