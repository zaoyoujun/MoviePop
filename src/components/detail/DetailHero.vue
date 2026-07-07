/**
 * 详情页 Hero 区域组件
 * 包含：海报背景、封面图、标题、元信息、标签、简介、操作按钮
 */
<template>
  <section
    class="detail-hero"
    :style="{ backgroundImage: `url(${backdrop})` }"
  >
    <!-- 渐变遮罩层 -->
    <div class="hero-overlay"></div>

    <!-- 返回按钮（固定在左上角） -->
    <button class="back-btn" @click="goBack" title="返回">
      <n-icon size="20"><ChevronBack /></n-icon>
      <span>返回</span>
    </button>

    <!-- 主内容区域 -->
    <div class="detail-content">
      <!-- 封面图 -->
      <img class="detail-poster" :src="poster" :alt="title" />

      <!-- 信息区域 -->
      <div class="detail-main">
        <!-- 标题 -->
        <h1 class="detail-title">{{ title }}</h1>

        <!-- 元信息 -->
        <div class="detail-meta">
          <span class="meta-item" v-if="year">
            <n-icon><CalendarOutline /></n-icon>
            {{ year }}
          </span>
          <span class="meta-item" v-if="country">
            <n-icon><LocationOutline /></n-icon>
            {{ country }}
          </span>
          <span class="meta-item" v-if="extraInfo">
            <n-icon><TvOutline /></n-icon>
            {{ extraInfo }}
          </span>
          <span class="meta-item" v-else-if="duration">
            <n-icon><TimeOutline /></n-icon>
            {{ duration }}
          </span>
          <span class="rating-badge" v-if="rating">
            <n-icon><Star /></n-icon>
            {{ rating }}
          </span>
        </div>

        <!-- 标签 -->
        <div class="detail-tags">
          <n-tag v-for="tag in tags" :key="tag" round>{{ tag }}</n-tag>
        </div>

        <!-- 简介 -->
        <p class="detail-desc">{{ description }}</p>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <n-button
            type="primary"
            size="large"
            class="btn-play"
            @click="$emit('play')"
          >
            <template #icon>
              <n-icon><Play /></n-icon>
            </template>
            立即播放
          </n-button>

          <n-button
            size="large"
            secondary
            class="btn-favorite"
            @click="$emit('favorite')"
          >
            <template #icon>
              <n-icon><Heart /></n-icon>
            </template>
            {{ isFavorite ? '已收藏' : '收藏' }}
          </n-button>

          <n-button
            size="large"
            secondary
            class="btn-folder"
            @click="$emit('scrape')"
          >
            <template #icon>
              <n-icon><FolderOutline /></n-icon>
            </template>
            手动刮削
          </n-button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
/**
 * 图标导入
 */
import {
  CalendarOutline,
  LocationOutline,
  TimeOutline,
  Star,
  Play,
  Heart,
  FolderOutline,
  TvOutline,
  ChevronBack
} from '@vicons/ionicons5'

/**
 * 路由实例（用于返回上一页）
 */
import { useRouter } from 'vue-router'
const router = useRouter()

/**
 * 返回上一页
 */
function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/home')
  }
}

/**
 * ==================== 属性定义 ====================
 */
defineProps({
  // 背景海报 URL
  backdrop: {
    type: String,
    default: ''
  },
  // 封面图 URL
  poster: {
    type: String,
    default: ''
  },
  // 标题
  title: {
    type: String,
    default: ''
  },
  // 年份
  year: {
    type: [String, Number],
    default: ''
  },
  // 国家
  country: {
    type: String,
    default: ''
  },
  // 时长
  duration: {
    type: String,
    default: ''
  },
  // 评分
  rating: {
    type: [String, Number],
    default: ''
  },
  // 标签数组
  tags: {
    type: Array,
    default: () => []
  },
  // 简介描述
  description: {
    type: String,
    default: ''
  },
  // 是否已收藏
  isFavorite: {
    type: Boolean,
    default: false
  },
  // 额外信息（如剧集显示"4季 · 36集"）
  extraInfo: {
    type: String,
    default: ''
  }
})

/**
 * 定义事件
 */
defineEmits(['play', 'favorite', 'scrape'])
</script>

<style scoped>
/* ==================== 返回按钮 ==================== */
.back-btn {
  position: absolute;
  top: 24px;
  left: 24px;
  z-index: 10;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  font-size: 14px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: rgba(0, 0, 0, 0.65);
  transform: translateX(-2px);
  border-color: rgba(124, 92, 255, 0.6);
}

/* ==================== Hero 区域样式 ==================== */
.detail-hero {
  position: relative;
  min-height: 500px;
  background-size: cover;
  background-position: center;
  padding: 80px 0 60px;
}

/* 渐变遮罩 */
.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to top,
    #0a0a0f 0%,
    rgba(10, 10, 15, 0.85) 40%,
    rgba(10, 10, 15, 0.5) 70%,
    transparent 100%
  );
}

/* 主内容容器 */
.detail-content {
  position: relative;
  z-index: 2;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 40px;
  display: flex;
  gap: 32px;
  align-items: flex-end;
}

/* 封面图 */
.detail-poster {
  flex-shrink: 0;
  width: 220px;
  height: 320px;
  border-radius: 16px;
  object-fit: cover;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

/* 信息区域 */
.detail-main {
  flex: 1;
  padding-bottom: 20px;
}

/* 标题 */
.detail-title {
  font-size: 42px;
  font-weight: 700;
  margin-bottom: 16px;
  line-height: 1.2;
  text-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

/* 元信息行 */
.detail-meta {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-bottom: 16px;
  color: #a0a0b0;
  font-size: 15px;
}

/* 单个元信息项 */
.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 评分徽章 */
.rating-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
  border-radius: 6px;
  font-weight: 600;
}

/* 标签容器 */
.detail-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.detail-tags .n-tag {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #a0a0b0;
}

/* 简介描述 */
.detail-desc {
  max-width: 700px;
  line-height: 1.7;
  color: #d0d0e0;
  font-size: 15px;
  margin-bottom: 28px;
}

/* 操作按钮组 */
.action-buttons {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

/* 播放按钮 */
.btn-play {
  background: #6366f1;
  border-color: #6366f1;
}

.btn-play:hover {
  background: #818cf8;
  border-color: #818cf8;
}

/* 收藏和文件夹按钮 */
.btn-favorite,
.btn-folder {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #ffffff;
}

.btn-favorite:hover,
.btn-folder:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* ==================== 响应式样式 ==================== */
@media (max-width: 768px) {
  .detail-hero {
    min-height: auto;
    padding-top: 40px;
  }

  .detail-content {
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 0 20px 40px;
  }

  .detail-poster {
    width: 180px;
    height: 260px;
  }

  .detail-title {
    font-size: 28px;
  }

  .detail-meta {
    justify-content: center;
    flex-wrap: wrap;
  }

  .detail-tags {
    justify-content: center;
  }

  .action-buttons {
    justify-content: center;
  }
}
</style>
