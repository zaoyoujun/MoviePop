<template>
  <article class="stat-card">
    <div class="stat-icon" :class="tone">
      <n-icon><component :is="icon" /></n-icon>
    </div>
    <div>
      <strong>{{ value }}</strong>
      <span>{{ label }}</span>
      <small>{{ help }}</small>
    </div>
  </article>
</template>

<script setup>
const props = defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    required: true
  },
  help: {
    type: String,
    default: ''
  },
  icon: {
    type: Object,
    required: true
  },
  tone: {
    type: String,
    default: 'violet',
    validator: (value) => ['violet', 'blue', 'orange', 'indigo'].includes(value)
  }
})
</script>

<style scoped>
.stat-card {
  display: flex;
  gap: 16px;
  align-items: center;
  min-width: 0;
  padding: 0 24px;
  border-right: 1px solid rgba(255, 255, 255, 0.18);
}

.stat-card:last-child {
  border-right: 0;
}

.stat-icon {
  display: grid;
  place-items: center;
  flex: 0 0 62px;
  height: 62px;
  border-radius: 8px;
  font-size: 28px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
}

.stat-icon.violet { 
  color: #bd93ff; 
  background: linear-gradient(135deg, rgba(128, 75, 255, 0.62), rgba(72, 42, 144, 0.54)); 
}
.stat-icon.blue { 
  color: #b7ccff; 
  background: linear-gradient(135deg, rgba(73, 103, 255, 0.58), rgba(30, 58, 138, 0.5)); 
}
.stat-icon.orange { 
  color: #ffd09a; 
  background: linear-gradient(135deg, rgba(255, 132, 46, 0.58), rgba(120, 65, 29, 0.5)); 
}
.stat-icon.indigo { 
  color: #b9b8ff; 
  background: linear-gradient(135deg, rgba(92, 96, 255, 0.58), rgba(39, 45, 119, 0.5)); 
}

.stat-card strong {
  display: block;
  color: #fff;
  font-size: 26px;
  line-height: 1;
}

.stat-card span {
  display: block;
  margin-top: 4px;
  color: #eef2ff;
  font-size: 15px;
}

.stat-card small {
  display: block;
  margin-top: 3px;
  color: #97a2b9;
  font-size: 12px;
}
</style>