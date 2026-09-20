import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import Layout from '@/views/Layout.vue'
import { get } from '@/api/request'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'favorites',
        name: 'Favorites',
        component: () => import('@/views/Favorites.vue'),
        meta: { title: '收藏' }
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('@/views/Stats.vue'),
        meta: { title: '观影统计' }
      },
      {
        path: 'pool',
        name: 'Pool',
        component: () => import('@/views/Pool.vue'),
        meta: { title: '影视数据库' }
      },
      {
        path: 'server',
        name: 'Server',
        component: () => import('@/views/Server.vue'),
        meta: { title: '服务器' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '设置' }
      }
    ]
  },
  {
    path: '/movie/:id',
    name: 'MovieDetail',
    component: () => import('@/views/MovieDetail.vue'),
    meta: { title: '影视详情' }
  },
  {
    path: '/online',
    name: 'Online',
    component: () => import('@/views/Online.vue'),
    meta: { title: '在线浏览' }
  },
  {
    path: '/first-boot',
    name: 'FirstBoot',
    component: () => import('@/views/FirstBoot.vue'),
    meta: { title: '初始化数据' }
  },
  ]

const router = createRouter({
  history: window.location.protocol === 'file:' ? createWebHashHistory() : createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  }
})

// 首次启动守卫：若虚拟片库为空且未访问过引导页，跳转到 /first-boot。
// 关键：这是全局 async 守卫，若里面的 await 意外挂起（后端无响应），
// 会导致整站所有菜单导航都卡死。因此：
//  1) 进入即标记 _bootChecked，保证只检查一次，后续导航同步放行；
//  2) count 请求加 4 秒超时；
//  3) 任何失败/超时都放行，绝不阻塞页面。
let _bootChecked = false
router.beforeEach(async (to) => {
  if (_bootChecked) return true
  _bootChecked = true
  if (to.name === 'FirstBoot') {
    return true
  }
  try {
    const data = await Promise.race([
      get('/pool/count'),
      new Promise((resolve, reject) => setTimeout(() => reject(new Error('boot-check-timeout')), 4000))
    ])
    const count = data?.count ?? 0
    if (count === 0) {
      return { name: 'FirstBoot' }
    }
  } catch (err) {
    // 后端不可用或超时时不阻塞，允许进入应用
  }
  return true
})

export default router
