<template>
  <n-layout has-sider class="movie-shell">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed="collapsed"
      :collapsed-width="72"
      :width="208"
      :native-scrollbar="false"
      class="movie-sider"
    >
      <div class="sider-frame">
        <div class="brand-bar">
          <div class="brand-mark">M</div>
          <div v-if="!collapsed" class="brand-copy">
            <strong>MoviePop</strong>
            <span>私人电影库</span>
          </div>
          <n-button
            quaternary
            circle
            size="small"
            class="collapse-btn"
            @click="collapsed = !collapsed"
          >
            <template #icon>
              <n-icon>
                <ChevronBackOutline v-if="!collapsed" />
                <ChevronForwardOutline v-else />
              </n-icon>
            </template>
          </n-button>
        </div>

        <n-menu
          :collapsed="collapsed"
          :collapsed-width="72"
          :collapsed-icon-size="21"
          :options="primaryMenuOptions"
          :value="activeKey"
          item-height="44px"
          @update:value="handleMenuClick"
        />

        <div class="category-block">
          <div v-if="!collapsed" class="section-title">媒体分类</div>
          <div class="category-scroll">
            <n-menu
              :collapsed="collapsed"
              :collapsed-width="72"
              :collapsed-icon-size="20"
              :options="categoryMenuOptions"
              :value="categoryKey"
              item-height="42px"
              @update:value="handleCategoryClick"
            />
          </div>
        </div>

        <div class="sider-bottom">
          <n-menu
            :collapsed="collapsed"
            :collapsed-width="72"
            :collapsed-icon-size="21"
            :options="bottomMenuOptions"
            :value="activeKey"
            item-height="42px"
            @update:value="handleMenuClick"
          />
        </div>
      </div>
    </n-layout-sider>

    <n-layout class="content-layout">
      <n-layout-content
        :native-scrollbar="false"
        class="movie-content"
        content-style="min-height: 100%;"
      >
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NIcon } from 'naive-ui'
import { getHomeData } from '@/api/movie'
import {
  AlbumsOutline,
  BarChartOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  FilmOutline,
  GridOutline,
  HeartOutline,
  HomeOutline,
  MusicalNotesOutline,
  PlayCircleOutline,
  ServerOutline,
  SettingsOutline,
  SparklesOutline,
  TvOutline,
  VideocamOutline
} from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const availableCategories = ref(new Set())

const activeKey = computed(() => route.name)
const categoryKey = computed(() =>
  route.name === 'Home' ? route.query.category || 'all' : null
)

async function loadAvailableCategories() {
  try {
    const data = await getHomeData({ limit: '1000' })
    const items = Array.isArray(data?.items) ? data.items : []
    const categories = new Set()
    items.forEach(item => {
      if (Array.isArray(item.categories)) {
        item.categories.forEach(cat => categories.add(cat))
      } else if (item.category) {
        categories.add(item.category)
      }
    })
    availableCategories.value = categories
  } catch (error) {
    console.error('加载分类失败', error)
    availableCategories.value = new Set()
  }
}

onMounted(loadAvailableCategories)
watch(() => route.name, (name) => {
  if (name === 'Home') {
    loadAvailableCategories()
  }
})

function renderIcon(icon) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

function handleMenuClick(key) {
  router.push({ name: key })
}

function handleCategoryClick(key) {
  router.push({
    name: 'Home',
    query: key === 'all' ? {} : { category: key }
  })
}

const primaryMenuOptions = [
  { label: '首页', key: 'Home', icon: renderIcon(HomeOutline) },
  { label: '收藏', key: 'Favorites', icon: renderIcon(HeartOutline) },
  { label: '观影统计', key: 'Stats', icon: renderIcon(BarChartOutline) },
  { label: '影视数据库', key: 'Pool', icon: renderIcon(FilmOutline) }
]

const movieCategories = [
  { label: '全部', key: 'all', icon: GridOutline },
  { label: '电影', key: 'movie', icon: FilmOutline },
  { label: '剧集', key: 'series', icon: TvOutline },
  { label: '动漫', key: 'anime', icon: SparklesOutline },
  { label: '综艺', key: 'variety', icon: VideocamOutline },
  { label: '音乐', key: 'music', icon: MusicalNotesOutline },
  { label: '短片', key: 'shorts', icon: PlayCircleOutline },
  { label: '纪录', key: 'documentary', icon: AlbumsOutline }
]

const categoryMenuOptions = computed(() => {
  return movieCategories.filter((item) => {
    if (item.key === 'all') return true
    return availableCategories.value.has(item.key)
  }).map((item) => ({
    label: item.label,
    key: item.key,
    icon: renderIcon(item.icon)
  }))
})

const bottomMenuOptions = [
  { label: '服务器', key: 'Server', icon: renderIcon(ServerOutline) },
  { label: '设置', key: 'Settings', icon: renderIcon(SettingsOutline) }
]
</script>

<style scoped>
.movie-shell {
  height: 100%;
  min-height: 0;
  color: #f8f3e9;
  background: #030506;
  overflow: hidden;
}

.movie-sider {
  height: 100%;
  background:
    linear-gradient(180deg, rgba(11, 17, 19, 0.98), rgba(5, 8, 10, 0.98)),
    #05080a;
}

.movie-sider :deep(.n-layout-sider__border) {
  background: rgba(255, 255, 255, 0.08);
}

.movie-sider :deep(.n-layout-sider-scroll-container) {
  height: 100%;
  overflow: hidden !important;
}

.movie-sider :deep(.n-scrollbar-content) {
  height: 100%;
}

.sider-frame {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 18px 12px;
  overflow: hidden;
}

.brand-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  margin-bottom: 18px;
}

.brand-mark {
  display: grid;
  place-items: center;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  color: #fff;
  font-weight: 900;
  background: linear-gradient(135deg, #667eea, #764ba2);
  box-shadow: 0 0 30px rgba(102, 126, 234, 0.3);
}

.brand-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.brand-copy strong {
  color: #fff5dc;
  font-size: 18px;
  line-height: 1.08;
}

.brand-copy span {
  margin-top: 5px;
  color: rgba(248, 243, 233, 0.52);
  font-size: 12px;
}

.collapse-btn {
  flex: 0 0 auto;
  color: rgba(248, 243, 233, 0.62);
}

.category-block {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  min-height: 0;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.category-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: 2px;
}

.category-scroll::-webkit-scrollbar {
  width: 4px;
}

.category-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(232, 199, 131, 0.28);
}

.section-title {
  margin: 0 12px 9px;
  color: rgba(248, 243, 233, 0.42);
  font-size: 12px;
}

.sider-bottom {
  flex: 0 0 auto;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.content-layout {
  height: 100%;
  min-height: 0;
  background:
    radial-gradient(circle at 72% -18%, rgba(214, 169, 76, 0.13), transparent 34%),
    radial-gradient(circle at 16% 8%, rgba(70, 213, 197, 0.1), transparent 30%),
    #030506;
}

.movie-content {
  height: 100%;
  min-height: 0;
}

.movie-content :deep(.n-layout-scroll-container) {
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.movie-shell :deep(.n-menu) {
  background: transparent;
}

.movie-shell :deep(.n-menu-item) {
  height: 44px;
  margin: 0 0 7px;
}

.movie-shell :deep(.n-menu-item-content) {
  height: 44px;
  border-radius: 8px;
  color: rgba(248, 243, 233, 0.68);
  transition:
    color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.movie-shell :deep(.n-menu-item-content:hover) {
  color: #fff7e8;
  background: rgba(255, 255, 255, 0.07);
  transform: translateX(2px);
}

.movie-shell :deep(.n-menu-item-content--selected) {
  color: #5bc4f7;
  background:
    linear-gradient(90deg, rgba(91, 47, 116, 0.4), rgba(26, 13, 33, 0.3));
  box-shadow:
    inset 3px 0 0 #667eea,
    0 12px 26px rgba(0, 0, 0, 0.24);
}

.movie-shell :deep(.n-menu-item-content--selected::before) {
  display: none;
}

.movie-shell :deep(.n-menu-item-content__icon) {
  color: currentColor;
}

.movie-shell :deep(.n-menu-item-content--selected .n-menu-item-content__icon) {
  color: #5bc4f7 !important;
}

.movie-shell :deep(.n-menu-item-content--selected .n-menu-item-content-header) {
  color: #5bc4f7 !important;
}

.movie-shell :deep(.n-layout-sider--collapsed .n-menu-item-content) {
  position: relative;
  display: flex;
  justify-content: center;
  width: 44px;
  margin: 0 auto;
  padding: 0 !important;
}

.movie-shell :deep(.n-layout-sider--collapsed .n-menu-item-content-header) {
  display: none;
}

.movie-shell :deep(.n-layout-sider--collapsed .n-menu-item-content__icon) {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin: 0 !important;
  transform: translate(-50%, -50%);
}
</style>

