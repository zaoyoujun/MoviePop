<!--
  扫描进度悬浮窗（全局组件）

  通过 useScanToast 提供的模块单例状态读取数据，
  放在 App.vue 中路由之外，切换页面不会消失，
  仅在扫描完成（status=done）或手动隐藏时关闭。
-->
<template>
  <transition name="scan-toast-fade">
    <div
      v-if="toast.visible"
      class="scan-toast"
      :class="`scan-toast-${toast.status}`"
    >
      <div class="scan-toast-icon">
        <div v-if="toast.status === 'scanning'" class="scan-spinner"></div>
        <div v-else-if="toast.status === 'cancelled'" class="scan-cancelled">&#10005;</div>
        <div v-else-if="toast.status === 'error'" class="scan-cross">!</div>
        <div v-else class="scan-check">&#10003;</div>
      </div>
      <div class="scan-toast-content">
        <div class="scan-toast-title">资源库扫描</div>
        <div class="scan-toast-message">{{ toast.message }}</div>
        
        <!-- 扫描进度条 -->
        <div v-if="toast.status === 'scanning' || toast.status === 'cancelled'" class="scan-progress-container">
          <div class="scan-progress-bar">
            <div 
              class="scan-progress-fill" 
              :style="{ width: toast.progress + '%' }"
            ></div>
          </div>
          <div class="scan-progress-text">
            {{ toast.processedFiles }} / {{ toast.totalFiles }}
          </div>
        </div>
        
        <!-- 当前处理文件（已隐藏，主文案已包含文件名信息） -->
        <!-- <div 
          v-if="toast.status === 'scanning' && toast.currentFile" 
          class="scan-current-file"
        >
          {{ toast.currentFile }}
        </div> -->
      </div>
      <button
        v-if="toast.status === 'scanning'"
        class="scan-toast-cancel"
        aria-label="取消扫描"
        @click="cancelScan"
      >
        &#10005;
      </button>
      <button
        v-else
        class="scan-toast-close"
        aria-label="关闭"
        @click="hideScanToast"
      >
        &times;
      </button>
    </div>
  </transition>
</template>

<script setup>
import { scanToast, hideScanToast, cancelScan } from '@/composables/useScanToast'
const toast = scanToast
</script>

<style scoped>
.scan-toast {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(20, 24, 36, 0.95), rgba(30, 35, 50, 0.95));
  border: 1px solid rgba(105, 240, 198, 0.3);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 24px rgba(105, 240, 198, 0.15);
  min-width: 280px;
  max-width: 360px;
}

.scan-toast-done {
  border-color: rgba(105, 240, 198, 0.6);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 24px rgba(105, 240, 198, 0.4);
}

.scan-toast-error {
  border-color: rgba(255, 99, 132, 0.6);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 24px rgba(255, 99, 132, 0.3);
}

.scan-toast-cancelled {
  border-color: rgba(255, 170, 80, 0.6);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 24px rgba(255, 170, 80, 0.2);
}

.scan-toast-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 扫描中 - 旋转动画 */
.scan-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(50, 198, 255, 0.2);
  border-top-color: #32c6ff;
  border-radius: 50%;
  animation: scan-spin 0.8s linear infinite;
}

@keyframes scan-spin {
  to {
    transform: rotate(360deg);
  }
}

/* 完成 - 对勾 */
.scan-check {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #69f0c6, #32c6ff);
  color: #06121a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  animation: scan-pop 0.3s ease-out;
}

@keyframes scan-pop {
  0% { transform: scale(0); }
  60% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

/* 错误 - 警示 */
.scan-cross {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff6384, #ff3b5c);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  animation: scan-pop 0.3s ease-out;
}

.scan-cancelled {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ffaa50, #ff8c42);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  animation: scan-pop 0.3s ease-out;
}

.scan-toast-content {
  flex: 1;
  min-width: 0;
}

.scan-toast-title {
  font-size: 13px;
  color: #98a4b8;
  margin-bottom: 4px;
}

.scan-toast-message {
  font-size: 14px;
  color: #f6f8ff;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 进度条容器 */
.scan-progress-container {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.scan-progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.scan-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #69f0c6, #32c6ff);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.scan-progress-text {
  font-size: 12px;
  color: #98a4b8;
  min-width: 50px;
  text-align: right;
}

/* 当前处理文件 */
.scan-current-file {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 取消按钮（仅在扫描中显示） */
.scan-toast-cancel {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border: none;
  background: rgba(255, 99, 132, 0.16);
  color: #ff6384;
  border-radius: 50%;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.scan-toast-cancel:hover {
  background: rgba(255, 99, 132, 0.28);
  color: #ff809f;
}

/* 关闭按钮（仅在非扫描中显示） */
.scan-toast-close {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: #98a4b8;
  border-radius: 50%;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.scan-toast-close:hover {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}

/* 悬浮窗出现/消失动画 */
.scan-toast-fade-enter-active,
.scan-toast-fade-leave-active {
  transition: all 0.3s ease;
}

.scan-toast-fade-enter-from {
  opacity: 0;
  transform: translateX(40px);
}

.scan-toast-fade-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>
