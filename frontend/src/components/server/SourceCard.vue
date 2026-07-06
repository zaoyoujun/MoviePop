/**
 * 数据源卡片组件
 *
 * 功能：
 * 1. 显示数据源基本信息
 * 2. 统计数据（文件、电影、剧集等）
 * 3. 操作菜单（修改、重扫、删除）
 */
<template>
  <article
    class="source-card"
    :class="{ active: source.active }"
    :style="{ '--card-tint': source.tint }"
  >
    <!-- 菜单按钮 -->
    <button class="card-menu-button" type="button" @click="$emit('toggleMenu')">
      <n-icon><OptionsOutline /></n-icon>
    </button>

    <!-- 操作菜单 -->
    <div v-if="isMenuOpen" class="card-menu">
      <button type="button" @click="$emit('edit')">
        <n-icon><CreateOutline /></n-icon>
        修改
      </button>
      <button type="button" @click="$emit('rescan')">
        <n-icon><RefreshOutline /></n-icon>
        重扫
      </button>
      <button type="button" class="danger" @click="$emit('delete')">
        <n-icon><TrashOutline /></n-icon>
        删除
      </button>
    </div>

    <!-- 主信息 -->
    <div class="source-main">
      <strong>{{ source.name }}</strong>
      <span>{{ source.type }}</span>
    </div>

    <!-- 统计数据 -->
    <div class="source-stats">
      <span><b>{{ source.files }}</b> 文件</span>
      <span><b>{{ source.movies }}</b> 电影</span>
      <span><b>{{ source.series }}</b> 剧集</span>
      <span><b>{{ source.anime }}</b> 动漫</span>
      <span><b>{{ source.music }}</b> 音乐</span>
    </div>

    <!-- 未匹配数量 -->
    <p class="unmatched">未匹配 {{ source.unmatched }}</p>

    <!-- 海报条 -->
    <div class="poster-strip">
      <i v-for="index in 5" :key="index"></i>
    </div>

    <!-- 路径 -->
    <p class="source-path">{{ decodedPath }}</p>
  </article>
</template>

<script setup>
/**
 * ==================== 导入 ====================
 */
import { computed } from 'vue'
import {
  OptionsOutline,
  CreateOutline,
  RefreshOutline,
  TrashOutline
} from '@vicons/ionicons5'

/**
 * ==================== 属性定义 ====================
 */
const props = defineProps({
  // 数据源信息
  source: {
    type: Object,
    required: true
  },
  // 菜单是否打开
  isMenuOpen: {
    type: Boolean,
    default: false
  }
})

/**
 * ==================== 事件定义 ====================
 */
defineEmits(['toggleMenu', 'edit', 'rescan', 'delete'])

/**
 * ==================== 计算属性 ====================
 */

// 解码后的路径
const decodedPath = computed(() => {
  try {
    return decodeURIComponent(props.source.path)
  } catch {
    return props.source.path
  }
})
</script>

<style scoped>
/* ==================== 卡片样式 ==================== */
.source-card {
  position: relative;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(17, 25, 42, 0.82), rgba(7, 12, 22, 0.78));
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  transform-style: preserve-3d;
}

.source-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, var(--card-tint, rgba(105, 240, 198, 0.2)), transparent);
  opacity: 0;
  transition: opacity 0.35s ease;
  pointer-events: none;
}

.source-card:hover {
  border-color: var(--card-tint, rgba(105, 240, 198, 0.5));
  transform: translateY(-8px) rotateX(2deg);
  box-shadow:
    0 20px 40px rgba(0, 0, 0, 0.35),
    0 0 30px rgba(105, 240, 198, 0.1);
}

.source-card:hover::before {
  opacity: 1;
}

.source-card.active {
  border-color: var(--card-tint, #69f0c6);
  box-shadow: 0 0 20px rgba(105, 240, 198, 0.15);
}

.source-card.active:hover {
  box-shadow:
    0 20px 40px rgba(0, 0, 0, 0.35),
    0 0 40px rgba(105, 240, 198, 0.25);
}

/* ==================== 菜单按钮样式 ==================== */
.card-menu-button {
  position: absolute;
  top: 16px;
  right: 16px;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: #9ca8ba;
  cursor: pointer;
  transition: all 0.2s ease;
}

.card-menu-button:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #f6f8ff;
}

/* ==================== 操作菜单样式 ==================== */
.card-menu {
  position: absolute;
  top: 52px;
  right: 16px;
  z-index: 10;
  min-width: 120px;
  padding: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  background: #12121a;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
}

.card-menu button {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #f6f8ff;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.card-menu button:hover {
  background: rgba(255, 255, 255, 0.08);
}

.card-menu button.danger {
  color: #ff6b6b;
}

.card-menu button.danger:hover {
  background: rgba(255, 107, 107, 0.12);
}

/* ==================== 主信息样式 ==================== */
.source-main {
  margin-bottom: 16px;
}

.source-main strong {
  display: block;
  margin-bottom: 4px;
  font-size: 18px;
  color: #f6f8ff;
}

.source-main span {
  color: #9ca8ba;
  font-size: 13px;
}

/* ==================== 统计数据样式 ==================== */
.source-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 12px;
  color: #a8b2c3;
  font-size: 13px;
}

.source-stats b {
  color: #f6f8ff;
  font-weight: 600;
}

/* ==================== 未匹配样式 ==================== */
.unmatched {
  margin: 0 0 16px;
  color: #ff9f43;
  font-size: 12px;
}

/* ==================== 海报条样式 ==================== */
.poster-strip {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
}

.poster-strip i {
  flex: 1;
  height: 48px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
}

/* ==================== 路径样式 ==================== */
.source-path {
  margin: 0;
  color: #6b7280;
  font-size: 12px;
  word-break: break-all;
}
</style>
