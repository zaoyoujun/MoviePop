<script setup>
import { computed } from 'vue'
import { darkTheme } from 'naive-ui'
import { ScanToast, DetailTransition, WindowTitleBar } from '@/components/common'
import { isTestMode } from '@/utils/runtime'

const isDesktop = computed(() => window.location.protocol === 'file:' || Boolean(window.electronAPI))

const themeOverrides = {
  common: {
    borderRadius: '14px',
    borderRadiusSmall: '12px'
  },
  Button: {
    borderRadiusTiny: '10px',
    borderRadiusSmall: '12px',
    borderRadiusMedium: '14px',
    borderRadiusLarge: '16px'
  }
}
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-notification-provider>
        <div class="app-frame" :class="{ 'app-frame--desktop': isDesktop }">
          <div v-if="isTestMode" class="test-mode-banner">测试模式：当前使用模拟影视数据</div>
          <WindowTitleBar v-if="isDesktop" class="app-titlebar" />
          <div class="app-body">
            <router-view />
          </div>
        </div>
        <ScanToast />
        <DetailTransition />
      </n-notification-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.app-frame {
  width: 100%;
  height: 100vh;
  min-height: 0;
  background: #030506;
}

.app-frame--desktop {
  display: grid;
  grid-template-rows: 40px minmax(0, 1fr);
}

.app-titlebar {
  width: 100%;
  background:
    radial-gradient(circle at 16% -80%, rgba(116, 75, 162, 0.33), transparent 42%),
    linear-gradient(90deg, rgba(17, 20, 28, 0.99), rgba(10, 13, 18, 0.98));
  border-bottom: 1px solid rgba(161, 146, 255, 0.2);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.26);
  -webkit-app-region: drag;
}

.app-body {
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.test-mode-banner {
  position: fixed;
  z-index: 1000;
  right: 16px;
  bottom: 16px;
  padding: 8px 12px;
  border: 1px solid rgba(255, 194, 72, 0.42);
  border-radius: 8px;
  color: #ffe6a6;
  background: rgba(56, 35, 7, 0.9);
  font-size: 12px;
  pointer-events: none;
}
</style>
