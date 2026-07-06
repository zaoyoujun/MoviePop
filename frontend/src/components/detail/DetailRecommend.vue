/**
 * 详情页相关推荐组件
 * 显示推荐电影列表，支持点击跳转到详情页
 */
<template>
  <section class="section">
    <!-- 区块标题 -->
    <h2 class="section-title">
      <n-icon><CompassOutline /></n-icon>
      相关推荐
    </h2>

    <!-- 电影卡片网格 -->
    <div class="recommend-grid">
      <article
        v-for="movie in movies"
        :key="movie.id"
        class="movie-card"
        @click="handleClick(movie.id)"
      >
        <!-- 海报图 -->
        <img class="movie-poster" :src="movie.poster" :alt="movie.title" />

        <!-- 电影信息 -->
        <div class="movie-info">
          <div class="movie-title">{{ movie.title }}</div>
          <div class="movie-meta">
            <span>{{ movie.year }} · {{ movie.category }}</span>
            <span class="rating" v-if="movie.rating">{{ movie.rating }}</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
/**
 * ==================== 导入 ====================
 */
import { CompassOutline } from '@vicons/ionicons5'

/**
 * ==================== 属性定义 ====================
 */
defineProps({
  // 电影列表
  movies: {
    type: Array,
    default: () => []
  }
})

/**
 * ==================== 事件定义 ====================
 */
const emit = defineEmits(['select'])

/**
 * 点击电影卡片
 * @param {string} id - 电影 ID
 */
function handleClick(id) {
  emit('select', id)
}
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

/* ==================== 推荐列表样式 ==================== */
.recommend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
}

/* 电影卡片 */
.movie-card {
  border-radius: 12px;
  overflow: hidden;
  background: #12121a;
  cursor: pointer;
  transition: all 0.3s ease;
}

.movie-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
}

/* 海报图 */
.movie-poster {
  width: 100%;
  height: 240px;
  object-fit: cover;
}

/* 电影信息 */
.movie-info {
  padding: 12px;
}

/* 电影标题 */
.movie-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 元信息 */
.movie-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #a0a0b0;
}

/* 评分标签 */
.rating {
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}

/* ==================== 响应式样式 ==================== */
@media (max-width: 768px) {
  .recommend-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
  }

  .movie-poster {
    height: 180px;
  }
}
</style>
