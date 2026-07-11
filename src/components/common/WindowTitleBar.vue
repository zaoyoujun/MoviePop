<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { CloseOutline, CopyOutline, RemoveOutline, SquareOutline } from '@vicons/ionicons5'

const isDesktop = computed(() => window.location.protocol === 'file:' || Boolean(window.electronAPI))
const isMaximized = ref(false)
let removeMaximizeListener = null

onMounted(async () => {
  if (!window.electronAPI) return
  isMaximized.value = await window.electronAPI.isWindowMaximized()
  removeMaximizeListener = window.electronAPI.onWindowMaximized((value) => {
    isMaximized.value = value
  })
})

onUnmounted(() => {
  removeMaximizeListener?.()
})

function minimizeWindow() {
  window.electronAPI?.minimizeWindow()
}

async function toggleMaximizeWindow() {
  if (!window.electronAPI) return
  isMaximized.value = await window.electronAPI.toggleMaximizeWindow()
}

function closeWindow() {
  window.electronAPI?.closeWindow()
}
</script>

<template>
  <div v-if="isDesktop" class="window-titlebar">
    <div class="window-brand">
      <span class="window-brand-mark">M</span>
      <span class="window-title">MoviePop</span>
    </div>
    <div class="window-controls">
      <button
        type="button"
        class="window-control"
        aria-label="最小化"
        title="最小化"
        @click="minimizeWindow"
      >
        <n-icon><RemoveOutline /></n-icon>
      </button>
      <button
        type="button"
        class="window-control"
        :aria-label="isMaximized ? '还原' : '最大化'"
        :title="isMaximized ? '还原' : '最大化'"
        @click="toggleMaximizeWindow"
      >
        <n-icon>
          <CopyOutline v-if="isMaximized" />
          <SquareOutline v-else />
        </n-icon>
      </button>
      <button
        type="button"
        class="window-control window-control--close"
        aria-label="关闭"
        title="关闭"
        @click="closeWindow"
      >
        <n-icon><CloseOutline /></n-icon>
      </button>
    </div>
  </div>
</template>

<style scoped>
.window-titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding-left: 12px;
  user-select: none;
  -webkit-app-region: drag;
}

.window-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: rgba(248, 243, 233, 0.72);
  font-size: 12px;
  font-weight: 600;
}

.window-brand-mark {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 5px;
  color: #fff;
  background: linear-gradient(135deg, #667eea, #764ba2);
  box-shadow: none;
  font-size: 11px;
  font-weight: 800;
}

.window-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.window-controls {
  display: flex;
  align-items: center;
  height: 34px;
  -webkit-app-region: no-drag;
}

.window-control {
  display: grid;
  place-items: center;
  width: 46px;
  height: 34px;
  border: 0;
  color: rgba(248, 243, 233, 0.58);
  background: transparent;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.window-control:hover {
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.055);
}

.window-control--close:hover {
  color: #fff;
  background: rgba(216, 59, 59, 0.82);
}

.window-control :deep(.n-icon) {
  font-size: 16px;
}
</style>
