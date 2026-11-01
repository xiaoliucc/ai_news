/* ============================================================
   AGENT 对话常量与初始文案（原 frontend/src/mock/data.ts）
   生产代码不应从 `mock/` 目录取常量——接入真实 API 后这里只剩
   UI 初始态与限制，与"mock"无关，故移到 constants/（2026-11-01, H-4-5）。
   ============================================================ */

import type { ChatMessage } from '@/types'

/** 单条消息最大字符数（与后端 ChatRequest.message 的 max_length 对齐） */
export const MAX_MESSAGE_CHARS = 4000

/** 对话历史上限轮数（与后端 history max_length 对齐） */
export const MAX_HISTORY_TURNS = 20

/** 初始欢迎语 */
export const WELCOME_MESSAGE: ChatMessage = {
  role: 'assistant',
  content:
    '**AGENT TERMINAL ONLINE**\n\n我是你的 AI 研究情报助手，可以检索资料库、解读论文、分析趋势或触发数据采集。\n\n试试下方的快捷操作，或直接输入问题——例如：\n\n> 总结一下最近 3 天 Hacker News 上关于 Agent 的讨论\n\n*HISTORY: 0/20 ROUNDS*',
  timestamp: '2026-08-18T09:30:00+08:00',
}

/** 初始消息列表（重置对话用） */
export const INITIAL_MESSAGES: ChatMessage[] = [WELCOME_MESSAGE]

/** 演示历史（调试 loadHistory 用，非真实数据） */
export const DEMO_HISTORY: ChatMessage[] = [
  {
    role: 'user',
    content: '总结一下机器之心最近一周的报道重点',
    timestamp: '2026-08-17T20:12:00+08:00',
  },
  {
    role: 'assistant',
    content:
      '最近一周机器之心共收录 **9 篇**文章，主题集中在三块：\n\n1. **端侧大模型**（3 篇）——手机厂商 AI 竞赛与端侧小模型报告\n2. **具身智能**（3 篇）——人形机器人量产与 VLA 模型落地\n3. **行业合规**（2 篇）——金融大模型备案与安全评测\n\n其中《人形机器人成本降至 10 万元》讨论热度最高（score 189）。',
    timestamp: '2026-08-17T20:13:00+08:00',
    toolCalls: [
      { name: 'SEARCH', status: 'done' },
      { name: 'SUMMARIZE', status: 'done' },
    ],
  },
  {
    role: 'user',
    content: '推荐几篇值得读的 ArXiv 论文',
    timestamp: '2026-08-17T20:20:00+08:00',
  },
  {
    role: 'assistant',
    content:
      '根据近 7 天收藏与热度，推荐以下 3 篇：\n\n- **arxiv:2608.11842** Efficient Reasoning with Sparse Chain-of-Thought（token 减 10 倍，MATH 保持 97%）\n- **arxiv:2608.11097** Synthetic Data Beyond Alignment（验证器反馈训练数据）\n- **arxiv:2608.09877** Mobile ALOHA 2（家务操作成功率 +22%）\n\n其中前两篇属于推理效率方向，是本周讨论最集中的子领域。',
    timestamp: '2026-08-17T20:21:00+08:00',
    toolCalls: [
      { name: 'SEARCH', status: 'done' },
      { name: 'ANALYZE_TREND', status: 'done' },
    ],
  },
]

/** 快捷操作（点击后把 prompt 作为用户消息发出） */
export const QUICK_ACTIONS: Array<{ key: string; prompt: string }> = [
  { key: 'todaySummary', prompt: '总结今天的 AI 热点' },
  { key: 'researchTrends', prompt: '分析最近的研究趋势' },
  { key: 'recommendPapers', prompt: '推荐值得阅读的论文' },
  { key: 'triggerCollect', prompt: '立即触发一次数据采集' },
]
