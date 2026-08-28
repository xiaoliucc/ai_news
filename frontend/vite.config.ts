/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 单页 Dashboard：别名 @ 指向 src，开发端口 5173，/api 代理到后端 FastAPI
// 内网穿透后端隧道：读项目根 .env 的 PUBLIC_BACKEND_URL（后端 :8000 隧道），
// 拼上 /api 作为完整 API 前缀注入 import.meta.env.VITE_API_BASE；
// 留空 = 本地 /api（dev 由 vite proxy 转发到 :8000）
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '')
  const backendUrl = (env.PUBLIC_BACKEND_URL || '').trim().replace(/\/+$/, '')
  // 后端路由挂在 /api 前缀下：隧道根地址需拼 /api（防重复后缀）
  const apiBase = backendUrl ? `${backendUrl.replace(/\/api$/i, '')}/api` : '/api'

  // 内网穿透前端隧道域名：cpolar 等外部域名不在 Vite 默认 host 白名单
  // （DNS rebinding 防护，仅放行 localhost），需显式放行才能经隧道访问。
  // 放行策略（配置在 dev server 启动时读取一次，改 .env / 本文件需重启生效）：
  //   1) cpolar 免费版每次隧道重启子域随机变化，直接放行整个 .cpolar.top 域
  //      （Vite 支持 . 前缀通配所有子域），域名变了无需再改 .env；
  //   2) 若 PUBLIC_FRONTEND_URL 指向其他隧道服务商（ngrok 等），再精确放行其 host。
  const tunnelHosts: string[] = ['.cpolar.top']
  try {
    const frontendTunnel = (env.PUBLIC_FRONTEND_URL || '').trim().replace(/\/+$/, '')
    const tunnelHost = frontendTunnel ? new URL(frontendTunnel).host : undefined
    if (tunnelHost) tunnelHosts.push(tunnelHost)
  } catch {
    // 地址不合法时忽略，仅保留 cpolar 通配放行
  }

  return {
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
      // 显式监听 IPv4：Vite 默认 'localhost' 只绑 [::1]（IPv6），
      // cpolar 隧道转发目标为 127.0.0.1（IPv4）会连不上
      host: '127.0.0.1',
      port: 5173,
      // 放行内网穿透隧道域名：本地 host + cpolar 通配域 + .env 指定隧道域名
      allowedHosts: ['localhost', '127.0.0.1', '::1', ...tunnelHosts],
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
    define: {
      // 空字符串时 http 层回退本地 /api；修改根 .env 后需重启 dev / 重新 build
      'import.meta.env.VITE_API_BASE': JSON.stringify(apiBase),
    },
    test: {
      // 测试目录在项目根 tests/frontend/（与 Python 测试并列）
      include: ['../tests/frontend/**/*.test.ts'],
      environment: 'happy-dom',
      // 注：vitest 4 已移除 server.deps.moduleDirectories——
      // 裸依赖解析依赖 resolve.alias（pinia 显式指向真实 node_modules）
    },
  }
})
