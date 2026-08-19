/* ============================================================
   VUE ROUTER —— Named Views 三栏同屏渲染
   / → layout（sidebar + main + panel 三个视图同时渲染）
   main 区域内部由组件内 v-if 切换 Articles / Trends / Hotlist
   （配合 keep-alive 缓存视图状态）
   ============================================================ */

import { createRouter, createWebHashHistory } from 'vue-router'
import DashboardLayout from '@/layouts/DashboardLayout.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: DashboardLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          components: {
            sidebar: () => import('@/views/SourcesPanel.vue'),
            main: () => import('@/views/ArticlesView.vue'),
            panel: () => import('@/views/AgentChatPanel.vue'),
          },
          meta: { keepAlive: true },
        },
      ],
    },
  ],
})

export default router
