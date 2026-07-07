<template>
  <section class="stats-strip">
    <article v-for="item in stats" :key="item.label" class="stat-card">
      <div class="stat-icon" :class="item.tone">
        <n-icon>
          <component :is="item.icon" />
        </n-icon>
      </div>
      <div>
        <strong>{{ item.value }}</strong>
        <span>{{ item.label }}</span>
        <small>{{ item.help }}</small>
      </div>
    </article>
  </section>
</template>

<script setup>
defineProps({
  stats: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin: 18px 0 28px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.03)),
    rgba(10, 13, 14, 0.72);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.26);
  backdrop-filter: blur(18px);
}

.stat-card {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
  padding: 18px 22px;
  border-right: 1px solid rgba(255, 255, 255, 0.09);
}

.stat-card:last-child {
  border-right: 0;
}

.stat-icon {
  display: grid;
  place-items: center;
  flex: 0 0 42px;
  height: 42px;
  border-radius: 8px;
  color: #fff7e8;
  font-size: 22px;
  background: rgba(255, 255, 255, 0.08);
}

.stat-icon.violet,
.stat-icon.indigo {
  color: #f06f5c;
  background: rgba(240, 111, 92, 0.12);
}

.stat-icon.blue {
  color: #46d5c5;
  background: rgba(70, 213, 197, 0.12);
}

.stat-icon.orange {
  color: #5bc4f7;
  background: rgba(102, 126, 234, 0.13);
}

.stat-card strong {
  display: block;
  color: #fff7e8;
  font-size: 24px;
  line-height: 1;
}

.stat-card span {
  display: block;
  margin-top: 5px;
  color: rgba(248, 243, 233, 0.78);
  font-size: 14px;
}

.stat-card small {
  display: block;
  overflow: hidden;
  margin-top: 3px;
  color: rgba(248, 243, 233, 0.44);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1120px) {
  .stats-strip {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-card:nth-child(2) {
    border-right: 0;
  }

  .stat-card:nth-child(-n + 2) {
    border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  }
}

@media (max-width: 620px) {
  .stats-strip {
    grid-template-columns: 1fr;
  }

  .stat-card {
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  }

  .stat-card:last-child {
    border-bottom: 0;
  }
}
</style>
