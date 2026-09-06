/* ============================================================
   I18N —— 界面文案字典（中 / EN）
   用法：模板 {{ t('view.articles') }}，脚本 this.t('btn.send') 或 t('btn.send', lang)
   ============================================================ */

import { computed, ref } from 'vue'

export type Lang = 'zh' | 'en'

const dict = {
  group: {
    tech_community: { zh: '技术社区', en: 'TECH COMMUNITY' },
    academic: { zh: '学术', en: 'ACADEMIC' },
    chinese_media: { zh: '中文媒体', en: 'CHINESE MEDIA' },
  },
  srcLabel: {
    hackernews: { zh: '黑客新闻', en: 'HACKER NEWS' },
    arxiv: { zh: '预印本', en: 'ARXIV' },
    huggingface_papers: { zh: 'HF 论文', en: 'HF PAPERS' },
    rss: { zh: 'RSS 聚合', en: 'RSS 聚合' },
    github: { zh: 'GitHub 趋势', en: 'GITHUB TRENDING' },
    csdn: { zh: 'CSDN 热榜', en: 'CSDN HOT RANK' },
  },
  stat: {
    totalRuns: { zh: '总采集次数', en: 'TOTAL RUNS' },
    totalArticles: { zh: '文章总数', en: 'TOTAL ARTICLES' },
    lastCollection: { zh: '上次采集', en: 'LAST COLLECTION' },
    running: { zh: '采集中...', en: 'RUNNING...' },
    total: { zh: '总数', en: 'TOTAL' },
    thisWeek: { zh: '本周', en: 'THIS WEEK' },
    activeSources: { zh: '启用源', en: 'ACTIVE SOURCES' },
    avgScore: { zh: '平均分', en: 'AVG SCORE' },
  },
  view: {
    articles: { zh: '文章', en: 'ARTICLES' },
    trends: { zh: '趋势', en: 'TRENDS' },
    hotlist: { zh: '热榜', en: 'HOTLIST' },
  },
  chart: {
    articleFlow: { zh: '文章流量', en: 'ARTICLE FLOW' },
    tagFreq: { zh: '词频 TOP 10', en: 'TAG FREQUENCY · TOP 10' },
    sourceShare: { zh: '来源占比', en: 'SOURCE SHARE' },
  },
  hotlist: {
    today: { zh: '今日 TOP 10', en: 'TODAY TOP 10' },
    week: { zh: '近 7 天 TOP 10', en: 'WEEK TOP 10' },
  },
  sort: {
    latest: { zh: '最新', en: 'LATEST' },
    score: { zh: '热度', en: 'HOT' },
    relevance: { zh: '相关度', en: 'RELEVANCE' },
  },
  quick: {
    todaySummary: { zh: '今日摘要', en: 'TODAY SUMMARY' },
    researchTrends: { zh: '研究趋势', en: 'RESEARCH TRENDS' },
    recommendPapers: { zh: '推荐论文', en: 'RECOMMEND PAPERS' },
    triggerCollect: { zh: '触发采集', en: 'TRIGGER COLLECT' },
  },
  placeholder: {
    search: { zh: '搜索文章...', en: 'SEARCH ARTICLES...' },
    titleSummary: { zh: '搜索标题 / 摘要...', en: 'SEARCH TITLE / SUMMARY...' },
    sources: { zh: '来源', en: 'SOURCES' },
    sort: { zh: '排序', en: 'SORT' },
    agent: { zh: '向你的 AI 研究助手提问...', en: 'ASK YOUR AI RESEARCH ASSISTANT...' },
  },
  btn: {
    collect: { zh: '手动采集', en: 'COLLECT' },
    hintLink: { zh: 'AGENT 面板提问', en: 'ASK IN AGENT PANEL' },
    ai: { zh: 'AI 解读', en: 'AI DIGEST' },
    history: { zh: '历史', en: 'HISTORY' },
    clear: { zh: '清空', en: 'CLEAR' },
    send: { zh: '发送', en: 'SEND' },
    stop: { zh: '停止', en: 'STOP' },
    prev: { zh: '上一页', en: 'PREV' },
    next: { zh: '下一页', en: 'NEXT' },
  },
  misc: {
    online: { zh: '在线', en: 'ONLINE' },
    collecting: { zh: '采集中...', en: 'COLLECTING...' },
    calling: { zh: '调用中', en: 'CALLING' },
    searching: { zh: '正在搜索中', en: 'SEARCHING' },
    done: { zh: '完成', en: 'DONE' },
    never: { zh: '从未', en: 'NEVER' },
    justNow: { zh: '刚刚', en: 'JUST NOW' },
    hint: {
      zh: '本地搜索为客户端关键词过滤；需要语义检索请前往',
      en: 'Local search is keyword-based; for semantic search, go to',
    },
    emptyTitle: { zh: '未找到文章', en: 'NO ARTICLES FOUND' },
    emptySub: {
      zh: '调整时间范围 / 来源筛选，或尝试其他关键词',
      en: 'Adjust the time range / source filters, or try other keywords',
    },
    clearFilters: { zh: '清除筛选', en: 'CLEAR FILTERS' },
    results: { zh: '结果', en: 'RESULTS' },
    page: { zh: '页', en: 'PAGE' },
    zh: { zh: '中文', en: 'ZH' },
    en: { zh: '英文', en: 'EN' },
    history: { zh: '历史', en: 'HISTORY' },
    rounds: { zh: '轮', en: 'ROUNDS' },
    searchPrompt: { zh: '搜索与「', en: 'Search for "' },
    searchPromptEnd: { zh: '」相关的资料', en: '" related materials' },
    digestPrompt: { zh: '解读这篇文章：', en: 'Digest this article: ' },
    articleId: { zh: '文章 ID', en: 'article ID' },
    qualityLabel: { zh: 'AI 质量分', en: 'AI QUALITY' },
    warn: {
      zh: '至少保留一个启用的信息源（对应后端 400：ALL_SOURCES_DISABLED）',
      en: 'Keep at least one source enabled (backend 400: ALL_SOURCES_DISABLED)',
    },
    collected: { zh: '采集已触发', en: 'COLLECTION TRIGGERED' },
    themeTitle: { zh: '切换视觉主题（青 / 黄）', en: 'Toggle theme (CYAN / YELLOW)' },
    panelOpen: { zh: '展开 AI 对话面板', en: 'Expand AI panel' },
    panelClose: { zh: '折叠 AI 对话面板', en: 'Collapse AI panel' },
    favOn: { zh: '取消收藏', en: 'Remove favorite' },
    favOff: { zh: '收藏', en: 'Add favorite' },
  },
} as const

type Entry = { zh: string; en: string }

const lang = ref<Lang>('zh')

function t(path: string, l?: Lang): string {
  const target = l ?? lang.value
  let node: unknown = dict
  for (const key of path.split('.')) {
    if (node && typeof node === 'object' && key in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[key]
    } else {
      return path
    }
  }
  const entry = node as Entry
  return entry && entry[target] ? entry[target] : path
}

function toggleLang(): void {
  lang.value = lang.value === 'zh' ? 'en' : 'zh'
}

export function useI18n() {
  const current = computed(() => lang.value)
  return { lang: current, t, toggleLang }
}

/** 非组件环境（如图表 legend）取词 */
export function tr(path: string, l: Lang): string {
  return t(path, l)
}

export function getLang(): Lang {
  return lang.value
}
