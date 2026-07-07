/**
 * 详情页文件信息组件
 * 显示：存储路径、文件大小、画质、字幕、播放记录等信息
 */
<template>
  <section class="section">
    <!-- 区块标题 -->
    <h2 class="section-title">
      <n-icon><DocumentTextOutline /></n-icon>
      文件信息
    </h2>

    <!-- 信息卡片网格 -->
    <div class="info-grid">
      <!-- 存储路径 -->
      <div class="info-card">
        <div class="info-label">存储路径</div>
        <div class="info-value">{{ filePath }}</div>
      </div>

      <!-- 文件大小 -->
      <div class="info-card">
        <div class="info-label">文件大小</div>
        <div class="info-value">{{ fileSize }}</div>
      </div>

      <!-- 画质规格 -->
      <div class="info-card">
        <div class="info-label">画质规格</div>
        <div class="info-value">{{ quality }}</div>
      </div>

      <!-- 字幕信息 -->
      <div class="info-card">
        <div class="info-label">字幕信息</div>
        <div class="info-value">{{ subtitle || '暂无字幕' }}</div>
      </div>

      <!-- 最近播放 -->
      <div class="info-card">
        <div class="info-label">最近播放</div>
        <div class="info-value">{{ lastPlayed || '从未播放' }}</div>
      </div>

      <!-- 播放进度 -->
      <div class="info-card">
        <div class="info-label">播放进度</div>
        <div class="info-value">
          <template v-if="progress > 0">
            {{ progress }}% · {{ progressTime }}
          </template>
          <template v-else>未开始</template>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
/**
 * ==================== 导入 ====================
 */
import { computed } from 'vue'
import { DocumentTextOutline } from '@vicons/ionicons5'

/**
 * ==================== 属性定义 ====================
 */
const props = defineProps({
  // 存储路径
  filePath: {
    type: String,
    default: ''
  },
  // 文件大小
  fileSize: {
    type: String,
    default: ''
  },
  // 画质规格
  quality: {
    type: String,
    default: ''
  },
  // 字幕信息
  subtitle: {
    type: String,
    default: ''
  },
  // 最近播放时间
  lastPlayed: {
    type: String,
    default: ''
  },
  // 播放进度百分比
  progress: {
    type: Number,
    default: 0
  },
  // 总时长（分钟）
  totalMinutes: {
    type: Number,
    default: 0
  }
})

/**
 * ==================== 计算属性 ====================
 */

// 计算进度时间
const progressTime = computed(() => {
  const minutes = Math.floor(props.totalMinutes * props.progress / 100)
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return hours > 0 ? `${hours}小时${mins}分钟` : `${mins}分钟`
})
</script>

<style scoped>
/* ==================== 区块样式 ==================== */
.section {
  margin-bottom: 48px;
}

/* 区块标题 */
.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 20px;
  color: #ffffff;
}

/* 标题前的装饰线 */
.section-title::before {
  content: "";
  width: 4px;
  height: 20px;
  background: #6366f1;
  border-radius: 2px;
}

/* ==================== 信息卡片样式 ==================== */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

/* 单个信息卡片 */
.info-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 16px 20px;
}

/* 信息标签 */
.info-label {
  font-size: 13px;
  color: #a0a0b0;
  margin-bottom: 8px;
}

/* 信息值 */
.info-value {
  font-size: 14px;
  font-weight: 500;
  color: #ffffff;
  word-break: break-all;
}
</style>
