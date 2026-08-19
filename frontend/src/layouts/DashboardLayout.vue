<script setup lang="ts">
import { onMounted } from 'vue'
import TopBar from '@/components/TopBar.vue'
import { useSourcesStore } from '@/stores/sources'
import { useArticlesStore } from '@/stores/articles'
import { useAgentStore } from '@/stores/agent'
import { useLayoutStore } from '@/stores/layout'

const sourcesStore = useSourcesStore()
const articlesStore = useArticlesStore()
const agentStore = useAgentStore()
const layoutStore = useLayoutStore()

onMounted(() => {
  // 初始并行加载：源列表/统计 + 文章库 + Agent 欢迎语
  void sourcesStore.fetchSources()
  void articlesStore.fetchArticles()
  agentStore.loadInitial()
})
</script>

<template>
  <el-container class="dash" direction="vertical">
    <el-header class="dash__topbar" height="56px">
      <TopBar />
    </el-header>

    <el-container class="dash__body">
      <!-- 左侧：信息源管理（Named View: sidebar） -->
      <el-aside
        class="dash__aside"
        :width="layoutStore.sidebarCollapsed ? '64px' : '280px'"
      >
        <router-view name="sidebar" />
      </el-aside>

      <!-- 中间：文章 / 趋势 / 热榜（Named View: main，keep-alive 缓存） -->
      <el-main class="dash__main">
        <router-view name="main" v-slot="{ Component }">
          <keep-alive :include="['ArticlesView', 'TrendsView', 'HotlistView']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>

      <!-- 右侧：AI Agent 面板（Named View: panel，宽度滑动同 SOURCES 侧栏） -->
      <el-aside
        class="dash__panel"
        :class="{ 'is-open': layoutStore.panelVisible }"
        :width="layoutStore.panelVisible ? '360px' : '0px'"
      >
        <router-view name="panel" />
      </el-aside>
    </el-container>
  </el-container>
</template>

<style scoped>
.dash {
  height: 100vh;
  background: var(--bg);
  color: var(--fg);
  overflow: hidden;
}

.dash__topbar {
  flex: none;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.dash__body {
  height: calc(100vh - var(--topbar-h));
  overflow: hidden;
}

.dash__aside {
  flex: none;
  height: 100%;
  border-right: 1px solid var(--border);
  overflow: hidden;
  transition: width var(--dur) var(--ease-endfield);
}

.dash__main {
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  padding: 0;
  overflow: hidden;
}

.dash__panel {
  flex: none;
  height: 100%;
  border-left: 1px solid transparent;
  overflow: hidden;
  transition: width var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield);
}
.dash__panel.is-open {
  border-left-color: var(--border);
}
</style>
