import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },
    { path: '/favorites', name: 'favorites', component: () => import('../views/FavoriteView.vue') },
    { path: '/recent', name: 'recent', component: () => import('../views/RecentView.vue') },
    { path: '/local', name: 'local', component: () => import('../views/LocalView.vue') },
    { path: '/report', name: 'report', component: () => import('../views/ReportView.vue') },
    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
    { path: '/recommend', name: 'recommend', component: () => import('../views/RecommendView.vue') },
  ],
})

export default router
