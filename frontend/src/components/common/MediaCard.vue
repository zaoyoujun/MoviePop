<template>
  <article
    class="media-card"
    :class="{ 'no-cover': !cover }"
    :style="coverStyle"
  >
    <div v-if="!cover" class="cover-placeholder">
      <div class="placeholder-icon">🎬</div>
      <div class="placeholder-title">{{ title }}</div>
    </div>
    <div class="card-tags">
      <n-tag round size="small" class="card-type">{{ type }}</n-tag>
      <n-tag round size="small" class="year-tag">{{ year }}</n-tag>
    </div>
    <div class="card-footer">
      <strong>{{ title }}</strong>
      <div class="card-actions">
        <n-button size="small" class="source-pill">{{ source }}</n-button>
        <n-button size="small" type="primary" class="small-play" @click="handlePlay">
          <template #icon>
            <n-icon><Play /></n-icon>
          </template>
          播放
        </n-button>
        <n-button size="small" secondary class="small-save" @click="handleFavorite">
          <template #icon>
            <n-icon><Heart /></n-icon>
          </template>
          {{ isFavorite ? '已收藏' : '收藏' }}
        </n-button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { Play, Heart } from '@vicons/ionicons5'

const props = defineProps({
  id: {
    type: String,
    required: true
  },
  title: {
    type: String,
    default: '未命名影视'
  },
  type: {
    type: String,
    default: '影视'
  },
  year: {
    type: [String, Number],
    default: ''
  },
  source: {
    type: String,
    default: '未知'
  },
  cover: {
    type: String,
    default: ''
  },
  isFavorite: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['play', 'favorite', 'detail'])

/**
 * 封面背景样式
 * 当 cover 为空时使用纯色背景，不显示图片
 */
const coverStyle = computed(() => {
  if (!props.cover) {
    return {
      background: 'linear-gradient(135deg, #2a3550 0%, #1a2030 100%)'
    }
  }
  return {
    backgroundImage: `url(${props.cover})`
  }
})

function handlePlay() {
  emit('play', props.id)
}

function handleFavorite() {
  emit('favorite', props.id)
}
</script>

<style scoped>
.media-card {
  position: relative;
  display: block;
  min-height: 320px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  background-position: center;
  background-size: cover;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.3);
}

.media-card::after {
  position: absolute;
  inset: 0;
  content: "";
  background: linear-gradient(0deg, rgba(5, 9, 18, 0.92) 0%, rgba(5, 9, 18, 0.18) 58%);
}

.card-tags {
  position: absolute;
  z-index: 2;
  top: 14px;
  left: 14px;
  right: 14px;
  display: flex;
  justify-content: space-between;
}

.card-type {
  color: #e7f9ff;
  background: rgba(15, 31, 47, 0.72);
}

.year-tag {
  color: #fff;
  background: linear-gradient(135deg, #ff9a3d, #ff5f2d);
}

.card-footer {
  position: absolute;
  z-index: 2;
  left: 14px;
  right: 14px;
  bottom: 14px;
}

.card-footer strong {
  display: block;
  margin-bottom: 10px;
  color: #fff;
  font-size: 18px;
}

.card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

.source-pill,
.small-save {
  color: #f8fbff;
  background: rgba(9, 14, 24, 0.62);
}

.small-play {
  color: #06121a;
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
}

/* ==================== 无封面占位图 ==================== */
.media-card.no-cover::after {
  background: linear-gradient(0deg, rgba(5, 9, 18, 0.7) 0%, rgba(5, 9, 18, 0.2) 100%);
}

.cover-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 1;
}

.placeholder-icon {
  font-size: 64px;
  opacity: 0.5;
  filter: grayscale(0.3);
}

.placeholder-title {
  font-size: 18px;
  color: #d6e0f0;
  font-weight: 600;
  text-align: center;
  padding: 0 16px;
  word-break: break-all;
  opacity: 0.85;
}
</style>