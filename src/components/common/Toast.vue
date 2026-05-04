<script setup lang="ts">
</script>

<template>
  <div class="toast-host" id="toastHost"></div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  bottom: 24px;
  right: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 9999;
}
</style>
