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
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 40px;
  padding-left: 14px;
  user-select: none;
  -webkit-app-region: drag;
}

.window-titlebar::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 1px;
  content: '';
  background: linear-gradient(90deg, rgba(139, 124, 255, 0.62), rgba(91, 196, 247, 0.24) 45%, transparent 78%);
  pointer-events: none;
}

.window-brand {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  color: rgba(252, 249, 255, 0.9);
  font-size: 13.5px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.window-brand-mark {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid rgba(214, 208, 255, 0.36);
  border-radius: 8px;
  color: #fff;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.22), transparent 48%),
    linear-gradient(135deg, #7a72ec, #6042ac);
  box-shadow: 0 5px 14px rgba(89, 67, 174, 0.4);
  font-size: 12px;
  font-weight: 800;
}

.window-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.window-controls {
  position: relative;
  display: flex;
  align-items: center;
  height: 40px;
  -webkit-app-region: no-drag;
}

.window-control {
  display: grid;
  place-items: center;
  width: 48px;
  height: 40px;
  border: 0;
  color: rgba(229, 225, 240, 0.68);
  background: transparent;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.window-control:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.window-control--close:hover {
  color: #fff;
  background: linear-gradient(135deg, #e95262, #c93445);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}

.window-control :deep(.n-icon) {
  font-size: 17px;
}
</style>
