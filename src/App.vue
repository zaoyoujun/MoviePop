<script setup>
import { computed } from 'vue'
import { darkTheme } from 'naive-ui'
import { ScanToast, DetailTransition, WindowTitleBar } from '@/components/common'

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
  grid-template-rows: 34px minmax(0, 1fr);
}

.app-titlebar {
  width: 100%;
  background: rgba(23, 23, 24, 0.98);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  -webkit-app-region: drag;
}

.app-body {
  min-height: 0;
  height: 100%;
  overflow: hidden;
}
</style>
