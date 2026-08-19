import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

import '@/styles/variables.css'
import '@/styles/endfield-theme.css'

import App from '@/App.vue'
import router from '@/router'
import { bindTheme } from '@/composables/useTheme'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')

// 主题（data-theme）挂载到 body，支持 CYAN / YELLOW 双主题
bindTheme(document.body)
