/* ============================================================
   LAYOUT STORE —— 布局状态：侧栏折叠 / Agent 面板显隐 / 主区视图
   ============================================================ */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MainView } from '@/types'

export const useLayoutStore = defineStore('layout', () => {
  const sidebarCollapsed = ref(false)
  const panelVisible = ref(true)
  const currentMainView = ref<MainView>('articles')

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function togglePanel(): void {
    panelVisible.value = !panelVisible.value
  }

  function setMainView(view: MainView): void {
    currentMainView.value = view
  }

  return {
    sidebarCollapsed,
    panelVisible,
    currentMainView,
    toggleSidebar,
    togglePanel,
    setMainView,
  }
})
