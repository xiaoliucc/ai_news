/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 单页 Dashboard：别名 @ 指向 src，开发端口 5173，/api 代理到后端 FastAPI
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入：模板 <el-*> 组件与 ElMessage 等 API 自动导入
    AutoImport({
      imports: ['vue'],
      resolvers: [ElementPlusResolver()],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // vitest 场景：测试文件位于 root 外的 tests/frontend/，裸依赖解析失败，
      // 显式指向真实 node_modules（同路径，dev/build 行为不变）
      pinia: fileURLToPath(new URL('./node_modules/pinia', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // dev 时代理 /api 到后端（后端 CORS 配置保留作双保险）
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    // 允许读取项目根（vitest 测试位于 root 外的 tests/frontend/）
    fs: {
      allow: ['..'],
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 大 vendor 独立 chunk：缓存友好 + 主 chunk 瘦身
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          echarts: ['echarts', 'vue-echarts'],
        },
      },
    },
  },
  test: {
    // 测试目录在项目根 tests/frontend/（与 Python 测试并列）
    include: ['../tests/frontend/**/*.test.ts'],
    environment: 'happy-dom',
    server: {
      deps: {
        // 测试文件位于 vite root 之外：模块目录相对 root（frontend/）解析，
        // 项目根下的 frontend/node_modules 写作 '../frontend/node_modules'
        moduleDirectories: ['node_modules', '../frontend/node_modules'],
      },
    },
  },
})
