import { createApp } from 'vue'
import { createPinia } from 'pinia'
import VChart from 'vue-echarts'

import '@/styles/variables.css'
import '@/utils/echarts' // echarts 按需注册（line/bar/pie + Canvas）

import App from '@/App.vue'
import router from '@/router'
import { bindTheme } from '@/composables/useTheme'

// Element Plus 组件按需自动导入（unplugin-vue-components），locale 由 App.vue 的 el-config-provider 提供
const app = createApp(App)
app.use(createPinia())
app.use(router)
// vue-echarts 全局注册（TrendsView 使用 <v-chart>）
app.component('VChart', VChart)

// 主题（data-theme）挂载到 body，支持 CYAN / YELLOW 双主题
bindTheme(document.body)

// EP 组件样式由 unplugin-vue-components 在组件模块加载时注入（早于 mount），
// endfield-theme.css 必须在其之后加载才能覆盖 EP 默认白底输入框/下拉框，
// 故改用动态导入：保证注入顺序晚于所有 EP 按需样式，再挂载应用。
import('@/styles/endfield-theme.css').then(() => {
  app.mount('#app')
})
