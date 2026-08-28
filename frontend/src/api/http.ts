/* ============================================================
   HTTP 实例 —— axios 封装
   baseURL：API 前缀——内网穿透后端隧道（vite.config 注入
   VITE_API_BASE，已含 /api），为空则本地 '/api'
   （dev 由 vite proxy 转发到 :8000）
   拦截器：解包 data + 非 2xx 统一 ElMessage 报错
   ============================================================ */

import axios from 'axios'
// ElMessage 手动 deep import（包入口导入会拉全量 element-plus）
import { ElMessage } from 'element-plus/es/components/message/index'
import 'element-plus/es/components/message/style/css'

// 穿透地址为空时回退本地 /api；有值则跨域直连后端隧道（CORS 已放行前端隧道）
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const http = axios.create({
  baseURL: API_BASE,
  timeout: 120_000, // Agent 对话可能较慢（LLM + 向量检索）
})

/** 带类型的 GET（响应已被拦截器解包为 data） */
export async function get<T>(url: string, params?: object): Promise<T> {
  const res = await http.get(url, { params })
  return res.data as T
}

/** 带类型的 POST */
export async function post<T>(url: string, body?: object): Promise<T> {
  const res = await http.post(url, body)
  return res.data as T
}

/** 带类型的 PUT */
export async function put<T>(url: string, body?: object): Promise<T> {
  const res = await http.put(url, body)
  return res.data as T
}

// 响应拦截：非 2xx 统一提示（detail 优先）
http.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail: unknown = err.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '请求失败，请检查后端服务')
    return Promise.reject(err)
  },
)

export default http
