<script setup lang="ts">
</script>

<template>
  <div class="wizard-overlay">
    <div class="wizard-modal">
      <h2>欢迎使用鸡米花</h2>
      <p>首次运行需要配置媒体库来源。请前往设置页面进行配置。</p>
      <router-link to="/settings" class="primary-btn">前往设置</router-link>
    </div>
  </div>
</template>

<style scoped>
.wizard-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.wizard-modal {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 40px;
  max-width: 500px;
  text-align: center;
}

.wizard-modal h2 {
  margin: 0 0 12px;
  color: var(--text);
}

.wizard-modal p {
  color: var(--text-soft);
  margin: 0 0 24px;
}

.primary-btn {
  display: inline-block;
  background: var(--accent);
  color: #fff;
  padding: 10px 24px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  text-decoration: none;
}
</style>
