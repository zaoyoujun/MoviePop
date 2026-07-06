/**
 * 数据源网格组件
 *
 * 功能：展示数据源卡片列表
 */
<template>
  <section class="library-section">
    <!-- 区块标题 -->
    <h2>资源库</h2>

    <!-- 卡片网格 -->
    <div class="source-grid">
      <SourceCard
        v-for="source in sources"
        :key="source.id"
        :source="source"
        :is-menu-open="openedMenu === source.id"
        @toggle-menu="$emit('toggleMenu', source.id)"
        @edit="$emit('edit', source)"
        @rescan="$emit('rescan', source.id)"
        @delete="$emit('delete', source.id)"
      />
    </div>
  </section>
</template>

<script setup>
/**
 * 组件属性
 */
defineProps({
  // 数据源列表
  sources: {
    type: Array,
    default: () => []
  },
  // 当前打开的菜单 ID
  openedMenu: {
    type: String,
    default: ''
  }
})

/**
 * 组件事件
 */
defineEmits(['toggleMenu', 'edit', 'rescan', 'delete'])

// 导入卡片组件
import SourceCard from './SourceCard.vue'
</script>

<style scoped>
/* ==================== 区块样式 ==================== */
.library-section h2 {
  margin: 0 0 20px;
  font-size: 20px;
}

/* ==================== 卡片网格样式 ==================== */
.source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
</style>
