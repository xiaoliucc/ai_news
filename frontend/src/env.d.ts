/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API 前缀（vite.config 从根 .env PUBLIC_BACKEND_URL 注入，已拼 /api）；空 = 本地 /api */
  readonly VITE_API_BASE?: string
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const component: DefineComponent<{}, {}, any>
  export default component
}
