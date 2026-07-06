<template>
  <section class="showcase">
    <n-carousel
      v-if="items.length"
      autoplay
      draggable
      dot-type="line"
      class="hero-carousel"
    >
      <article
        v-for="item in items"
        :key="item.id"
        class="hero-slide"
      >
        <img :src="item.backdrop" :alt="item.title" class="hero-image" />
        <div class="hero-shade"></div>
        <div class="hero-copy">
          <span class="hero-kicker">正在推荐</span>
          <div class="title-row">
            <h1>{{ item.title }}</h1>
            <strong v-if="item.rating">{{ item.rating }}</strong>
            <span v-if="item.year">{{ item.year }}</span>
          </div>
          <p>{{ item.description || '从你的私人片库中挑选一部，继续今晚的放映。' }}</p>
          <div class="tag-row">
            <span v-for="tag in item.tags" :key="tag">{{ tag }}</span>
          </div>
          <div class="hero-actions">
            <button class="primary-action" @click="$emit('play', item.id)">
              <n-icon><Play /></n-icon>
              继续播放
            </button>
            <button class="ghost-action" @click="$emit('detail', item.id)">
              <n-icon><InformationCircleOutline /></n-icon>
              详情
            </button>
          </div>
        </div>
      </article>
    </n-carousel>

    <div v-else class="empty-showcase">
      <n-spin v-if="loading" size="large" />
      <n-empty v-else description="暂无海报数据" />
    </div>
  </section>
</template>

<script setup>
import { InformationCircleOutline, Play } from '@vicons/ionicons5'

defineProps({
  items: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['play', 'detail'])
</script>

<style scoped>
.showcase {
  position: relative;
  overflow: hidden;
  min-height: 330px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.empty-showcase {
  display: grid;
  place-items: center;
  min-height: 330px;
  background:
    radial-gradient(circle at 60% 12%, rgba(102, 126, 234, 0.2), transparent 32%),
    #050708;
}

.hero-carousel,
.hero-carousel :deep(.n-carousel),
.hero-carousel :deep(.n-carousel__slides),
.hero-carousel :deep(.n-carousel__slide) {
  height: 330px !important;
}

.hero-carousel :deep(.n-carousel__dots) {
  right: 34px;
  bottom: 22px;
  left: auto;
  transform: none;
  z-index: 7;
}

.hero-carousel :deep(.n-carousel__dot) {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: rgba(248, 243, 233, 0.3);
}

.hero-carousel :deep(.n-carousel__dot--active) {
  width: 24px;
  background: #667eea;
}

.hero-slide {
  position: relative;
  height: 330px;
  overflow: hidden;
}

.hero-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

.hero-slide::after {
  position: absolute;
  inset: auto 0 0;
  height: 44%;
  content: "";
  background: linear-gradient(180deg, transparent, #030506 92%);
}

.hero-shade {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(3, 5, 6, 0.94) 0%, rgba(91, 47, 116, 0.4) 36%, rgba(3, 5, 6, 0.12) 72%),
    linear-gradient(0deg, rgba(3, 5, 6, 0.42), rgba(3, 5, 6, 0.1));
}

.hero-copy {
  position: absolute;
  z-index: 3;
  top: 42px;
  left: clamp(24px, 3.8vw, 58px);
  max-width: min(660px, calc(100% - 56px));
}

.hero-kicker {
  color: #5bc4f7;
  font-size: 13px;
  font-weight: 800;
}

.title-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: baseline;
  margin-top: 6px;
}

.title-row h1 {
  max-width: 640px;
  color: #fff8ea;
  font-size: clamp(30px, 3.2vw, 44px);
  line-height: 1.02;
  letter-spacing: 0;
  text-shadow: 0 22px 44px rgba(0, 0, 0, 0.58);
}

.title-row strong {
  color: #ff8d6f;
  font-size: 16px;
}

.title-row span {
  color: rgba(248, 243, 233, 0.78);
  font-size: 16px;
}

.hero-copy p {
  max-width: 590px;
  margin: 10px 0 0;
  color: rgba(248, 243, 233, 0.72);
  font-size: 15px;
  line-height: 1.55;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 11px;
}

.tag-row span {
  padding: 6px 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  color: rgba(248, 243, 233, 0.84);
  background: rgba(12, 15, 16, 0.42);
  backdrop-filter: blur(12px);
  font-size: 12px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 13px;
}

.primary-action,
.ghost-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 20px;
  border-radius: 8px;
  cursor: pointer;
}

.primary-action {
  border: 1px solid rgba(102, 126, 234, 0.5);
  color: #fff;
  background: linear-gradient(135deg, #667eea, #764ba2);
  font-weight: 800;
  box-shadow: 0 18px 34px rgba(102, 126, 234, 0.3);
}

.ghost-action {
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(255, 248, 234, 0.9);
  background: rgba(12, 15, 16, 0.56);
  backdrop-filter: blur(14px);
}

.primary-action:hover,
.ghost-action:hover {
  transform: translateY(-2px);
}

@media (max-width: 760px) {
  .hero-carousel,
  .hero-carousel :deep(.n-carousel),
  .hero-carousel :deep(.n-carousel__slides),
  .hero-carousel :deep(.n-carousel__slide),
  .hero-slide {
    height: 430px !important;
  }

  .hero-copy {
    top: 46px;
  }

  .title-row h1 {
    font-size: 40px;
  }
}
</style>
