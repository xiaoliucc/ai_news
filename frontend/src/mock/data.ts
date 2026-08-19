/* ============================================================
   MOCK 数据层 —— 对应后端 FastAPI 各 API 的响应形态
   覆盖：GET /api/sources / PUT /api/sources/{name} /
   GET /api/stats / GET /api/articles / POST /api/agent/chat
   数据量：4 源、60+ 篇文章（14 天跨度、中英混合）
   ============================================================ */

import type {
  Article,
  ChatMessage,
  CollectionStats,
  Source,
  SourceName,
} from '@/types'

/* ---------- 锚点时间：运行环境 = 2026-08-18（Mock 以此为"当前"） ---------- */
export const MOCK_NOW = '2026-08-18T09:30:00+08:00'

/* ---------- 信息源（对应后端 SOURCE_META） ---------- */
export const mockSources: Source[] = [
  {
    name: 'hackernews',
    label: 'Hacker News',
    category: 'tech_community',
    description: 'AI 相关热门帖子与讨论',
    article_count: 156,
    enabled: true,
  },
  {
    name: 'arxiv',
    label: 'ArXiv',
    category: 'academic',
    description: 'cs.AI/cs.CL/cs.CV/cs.LG 等 11 分类新论文',
    article_count: 89,
    enabled: true,
  },
  {
    name: 'huggingface_papers',
    label: 'HF Papers',
    category: 'academic',
    description: '每日 AI 论文 + 代码实现',
    article_count: 67,
    enabled: true,
  },
  {
    name: 'rss',
    label: 'RSS 聚合',
    category: 'chinese_media',
    description: '中文源聚合（含机器之心官方 RSS）',
    article_count: 42,
    enabled: true,
  },
]

/* ---------- 采集统计（对应 GET /api/stats） ---------- */
export const mockStats: CollectionStats = {
  total_runs: 48,
  total_articles: 354,
  last_collection_at: '2026-08-18T07:30:00+08:00',
  runs: [
    {
      id: 48,
      started_at: '2026-08-18T07:20:00+08:00',
      finished_at: '2026-08-18T07:30:00+08:00',
      status: 'done',
      total_articles: 42,
      deduped_count: 6,
      source_stats: [
        { name: 'hackernews', fetched: 12, failed: false, error: null, elapsed_ms: 2200 },
        { name: 'arxiv', fetched: 10, failed: false, error: null, elapsed_ms: 3100 },
        { name: 'huggingface_papers', fetched: 12, failed: false, error: null, elapsed_ms: 1800 },
        { name: 'rss', fetched: 8, failed: false, error: null, elapsed_ms: 900 },
      ],
      error: null,
    },
    {
      id: 47,
      started_at: '2026-08-17T07:15:00+08:00',
      finished_at: '2026-08-17T07:26:00+08:00',
      status: 'done',
      total_articles: 38,
      deduped_count: 5,
      source_stats: [
        { name: 'hackernews', fetched: 11, failed: false, error: null, elapsed_ms: 2100 },
        { name: 'arxiv', fetched: 9, failed: false, error: null, elapsed_ms: 2900 },
        { name: 'huggingface_papers', fetched: 11, failed: false, error: null, elapsed_ms: 1700 },
        { name: 'rss', fetched: 7, failed: false, error: null, elapsed_ms: 850 },
      ],
      error: null,
    },
  ],
}

/* ---------- 精选种子文章（手工撰写，保证标题与摘要质量） ---------- */
const seedArticles: Article[] = [
  {
    id: 'hackernews:38291045',
    title: 'GPT-5 Technical Report: Scaling Laws Revisited',
    url: 'https://news.ycombinator.com/item?id=38291045',
    source: 'hackernews',
    summary:
      'OpenAI releases comprehensive technical report on GPT-5 training run: new scaling law exponents, data mix ablations, and surprising improvements in long-horizon agentic tasks.',
    author: 'OpenAI Research',
    published_at: '2026-08-17T14:30:00Z',
    score: 342,
    tags: ['LLM', 'Scaling', 'Technical Report'],
    language: 'en',
  },
  {
    id: 'hackernews:38288911',
    title: 'Show HN: I built a local-first RAG reader for 2,000 papers',
    url: 'https://news.ycombinator.com/item?id=38288911',
    source: 'hackernews',
    summary:
      'Self-hosted paper reader with ChromaDB + local LLM. No cloud, full-text search over ArXiv dump, and a minimal TUI. Users report 30ms retrieval over 2k papers on a laptop.',
    author: 'quantumdino',
    published_at: '2026-08-17T09:12:00Z',
    score: 287,
    tags: ['RAG', 'Local LLM', 'Show HN'],
    language: 'en',
  },
  {
    id: 'hackernews:38285502',
    title: 'The WebGPU inference race: 8-bit LLMs in the browser',
    url: 'https://news.ycombinator.com/item?id=38285502',
    source: 'hackernews',
    summary:
      'Community benchmark of WebGPU backends for 7B-class quantized models. Firefox finally ships fp16 compute, and WASM SIMD wins on memory-constrained devices.',
    author: 'webgpu-labs',
    published_at: '2026-08-16T16:45:00Z',
    score: 231,
    tags: ['Inference', 'WebGPU', 'Quantization'],
    language: 'en',
  },
  {
    id: 'hackernews:38279944',
    title: 'LLM agents keep reinventing the same tool-use pattern',
    url: 'https://news.ycombinator.com/item?id=38279944',
    source: 'hackernews',
    summary:
      'A taxonomy of tool-use loops across 40 agent frameworks shows 90% converge on the same observe-think-act cycle. Is the loop the product now?',
    author: 'agent-tracer',
    published_at: '2026-08-15T11:20:00Z',
    score: 198,
    tags: ['Agent', 'Tool Use'],
    language: 'en',
  },
  {
    id: 'hackernews:38273481',
    title: 'SVG + WebGPU: a GPU rasterizer that beats canvas for dashboards',
    url: 'https://news.ycombinator.com/item?id=38273481',
    source: 'hackernews',
    summary:
      '10M-point scatter renderer in ~200 lines. The demo renders 60fps on integrated graphics; the author open-sources the pipeline used by their analytics startup.',
    author: 'raster-ink',
    published_at: '2026-08-14T08:05:00Z',
    score: 165,
    tags: ['WebGPU', 'Data Viz'],
    language: 'en',
  },
  {
    id: 'arxiv:2608.11842',
    title: 'Efficient Reasoning with Sparse Chain-of-Thought: A 10x Token Reduction',
    url: 'https://arxiv.org/abs/2608.11842',
    source: 'arxiv',
    summary:
      'We show that most reasoning steps in long CoT traces are redundant and can be pruned by a small router, cutting inference tokens 10x while preserving 97% accuracy on MATH and GPQA.',
    author: 'L. Wang, S. Chen',
    published_at: '2026-08-17T18:00:00Z',
    score: 156,
    tags: ['LLM', 'Reasoning', 'Efficiency'],
    language: 'en',
  },
  {
    id: 'arxiv:2608.11097',
    title: 'Synthetic Data Beyond Alignment: Scaling Post-Training with Verifier Feedback',
    url: 'https://arxiv.org/abs/2608.11097',
    source: 'arxiv',
    summary:
      'A framework for generating synthetic reasoning traces guided by an automated verifier. On code and math benchmarks, verifier-guided data outperforms 3x more human-curated data.',
    author: 'M. Kuo, A. Patel',
    published_at: '2026-08-16T15:30:00Z',
    score: 132,
    tags: ['Synthetic Data', 'RL', 'Post-Training'],
    language: 'en',
  },
  {
    id: 'arxiv:2608.10520',
    title: 'Sparse Autoencoders for Vision: Interpreting Diffusion Model Neurons',
    url: 'https://arxiv.org/abs/2608.10520',
    source: 'arxiv',
    summary:
      'We train SAEs on diffusion model activations and discover interpretable direction features that control style, pose and lighting, enabling semantic editing via feature steering.',
    author: 'R. Okafor, D. Kim',
    published_at: '2026-08-15T09:40:00Z',
    score: 118,
    tags: ['Interpretability', 'Diffusion', 'CV'],
    language: 'en',
  },
  {
    id: 'arxiv:2608.09877',
    title: 'Mobile ALOHA 2: Scalable Teleoperation for Bimanual Household Manipulation',
    url: 'https://arxiv.org/abs/2608.09877',
    source: 'arxiv',
    summary:
      'An upgraded low-cost teleoperation platform for dual-arm manipulation. New wrist cameras and a learned residual policy improve success rates on 14 household tasks by 22%.',
    author: 'H. Zhao, Z. Fu, C. Finn',
    published_at: '2026-08-14T12:00:00Z',
    score: 104,
    tags: ['Embodied AI', 'Robotics', 'Imitation Learning'],
    language: 'en',
  },
  {
    id: 'huggingface_papers:2608.22014',
    title: 'FlashFlow: Streaming KV-Cache Offload with 4-bit Gradient Checkpoints',
    url: 'https://huggingface.co/papers/2608.22014',
    source: 'huggingface_papers',
    summary:
      'Paper + code: offloads KV cache to CPU/disk in a streaming ring buffer, cutting peak GPU memory 5x for 128k-context serving with <5% throughput loss.',
    author: 'FlashFlow Team',
    published_at: '2026-08-17T07:00:00Z',
    score: 96,
    tags: ['Inference', 'KV Cache', 'Serving'],
    language: 'en',
  },
  {
    id: 'huggingface_papers:2608.21593',
    title: 'RAG-Fusion-2: Query Rewriting with Cross-Encoder Reranking at Scale',
    url: 'https://huggingface.co/papers/2608.21593',
    source: 'huggingface_papers',
    summary:
      'Paper + code: a two-stage pipeline (LLM query rewrite → hybrid BM25/dense retrieval → cross-encoder rerank) that lifts RAG answer accuracy on 6 benchmarks by 11% on average.',
    author: 'HF Research',
    published_at: '2026-08-16T10:15:00Z',
    score: 88,
    tags: ['RAG', 'Retrieval', 'Reranking'],
    language: 'en',
  },
  {
    id: 'huggingface_papers:2608.20856',
    title: 'Whisper-3-Align: Forced Alignment for 200+ Languages',
    url: 'https://huggingface.co/papers/2608.20856',
    source: 'huggingface_papers',
    summary:
      'Paper + code: extends Whisper-3 with a CTC head for word-level timestamps, covering 200+ languages including low-resource ones; 30ms median alignment error on Common Voice.',
    author: 'AudioLab',
    published_at: '2026-08-15T05:30:00Z',
    score: 81,
    tags: ['Audio', 'ASR', 'Multimodal'],
    language: 'en',
  },
  {
    id: 'rss:rm-20260817-01',
    title: '机器之心：谷歌发布 Gemini 3 Pro，长上下文推理能力大幅提升',
    url: 'https://www.jiqizhixin.com/articles/2026-08-17-01',
    source: 'rss',
    summary:
      '谷歌在今日开发者大会上发布 Gemini 3 Pro，宣称在 200 万 token 长上下文基准上取得领先，并首次将原生多模态推理扩展到视频理解场景。',
    author: '机器之心',
    published_at: '2026-08-17T08:00:00+08:00',
    score: 214,
    tags: ['LLM', '多模态', 'Gemini'],
    language: 'zh',
  },
  {
    id: 'rss:rm-20260817-02',
    title: '智源研究院开源 1T 参数多模态模型，中文图文理解刷新 SOTA',
    url: 'https://www.jiqizhixin.com/articles/2026-08-17-02',
    source: 'rss',
    summary:
      '智源发布 Emu-3.5，1T 参数的统一多模态模型在中文图文理解榜单上超越 GPT-4o 与 Claude，并开源权重与训练数据过滤工具链。',
    author: '机器之心',
    published_at: '2026-08-17T14:20:00+08:00',
    score: 176,
    tags: ['多模态', '开源模型', '中文'],
    language: 'zh',
  },
  {
    id: 'rss:rm-20260816-01',
    title: '深度解读：具身智能机器人进厂，端到端 VLA 模型落地进展',
    url: 'https://www.jiqizhixin.com/articles/2026-08-16-01',
    source: 'rss',
    summary:
      '多家国内机器人公司披露端到端视觉-语言-动作模型在工厂场景的部署数据，成功率较传统分层方案提升约 18%，本文梳理其数据飞轮与技术路线差异。',
    author: '机器之心',
    published_at: '2026-08-16T10:00:00+08:00',
    score: 143,
    tags: ['具身智能', 'VLA', '机器人'],
    language: 'zh',
  },
  {
    id: 'rss:rm-20260815-01',
    title: '硅谷日报：Anthropic 公布 Context Engineering 最佳实践手册',
    url: 'https://www.jiqizhixin.com/articles/2026-08-15-01',
    source: 'rss',
    summary:
      'Anthropic 发布面向长上下文应用的工程手册，覆盖上下文压缩、检索路由与工具调用边界设计，被社区称为"Agent 应用必读"。',
    author: '硅谷日报',
    published_at: '2026-08-15T09:10:00+08:00',
    score: 129,
    tags: ['Agent', '上下文工程', '最佳实践'],
    language: 'zh',
  },
]

/* ---------- 生成式文章：主题池（保证标题质量与领域覆盖） ---------- */
interface TopicSeed {
  t: string // 英文标题
  c: string // 中文标题（rss 用）
  s: string // 英文摘要
  tags: string[]
}

const topicPool: TopicSeed[] = [
  { t: 'Scaling Sparse Mixture-of-Experts to 2T Parameters', c: '稀疏 MoE 扩展至 2T 参数：成本与效果的新平衡', s: 'We analyze training dynamics and routing collapse in 2T-parameter sparse MoE models, proposing entropy-regularized routing that stabilizes expert utilization across 5 domains.', tags: ['LLM', 'MoE', 'Scaling'] },
  { t: 'Reasoning-Enhanced Embeddings for Retrieval-Augmented Generation', c: '面向 RAG 的推理增强嵌入新方法', s: 'We augment dense embeddings with chain-of-thought-derived features, improving recall@20 by 9% on long-tail scientific queries without extra inference cost at query time.', tags: ['RAG', 'Embedding', 'Retrieval'] },
  { t: 'Chain-of-Verification: Self-Correction Loops for Factual Generation', c: '验证链：生成过程中的自纠错机制', s: 'A lightweight verification loop where the model drafts, verifies against retrieved evidence, and rewrites. Cuts hallucination rates by 41% on long-form generation.', tags: ['LLM', 'Hallucination', 'Verification'] },
  { t: 'Reinforcement Learning from Verifiable Feedback for Math Agents', c: '基于可验证反馈的数学智能体强化学习', s: 'We train math agents with RLVR on generated problem trees, achieving 92% pass@1 on a new 10k-question Olympiad-style benchmark.', tags: ['RL', 'Agent', 'Math'] },
  { t: 'FlashAttention-4: Sub-Quadratic Attention for 4M-Token Contexts', c: 'FlashAttention-4：面向 400 万 token 上下文的次二次注意力', s: 'Combining block-sparse attention with streaming memory offload, we reach 4M-token context at 2.3x throughput over FlashAttention-3, enabling full-book summarization on a single H100.', tags: ['Efficiency', 'Attention', 'Long Context'] },
  { t: 'Diffusion Policy 3: Closed-Loop Visuomotor Learning with 3D Priors', c: 'Diffusion Policy 3：引入 3D 先验的闭环视觉运动学习', s: 'Injecting 3D spatial priors into diffusion policies reduces sim-to-real gap: 74% success on unseen manipulation scenes, up from 51% for the prior version.', tags: ['Embodied AI', 'Diffusion', 'Robotics'] },
  { t: 'A Survey of Test-Time Compute Scaling in 2026', c: '2026 年推理时计算扩展研究综述', s: 'We survey 120+ works on test-time compute: search strategies, verifier design, and budget allocation. Includes a unified taxonomy and open benchmark suite.', tags: ['Test-Time Compute', 'Survey', 'LLM'] },
  { t: 'Tool-Use Transformers Learn to Simulate Small Programs', c: '工具使用型 Transformer 可模拟小型程序', s: 'Probing experiments show tool-use finetuning induces internal program simulation in hidden states, explaining emergent compositional tool chains.', tags: ['Agent', 'Interpretability', 'Tool Use'] },
  { t: 'Vision-Language Models as World Simulators for Embodied Agents', c: '视觉语言模型作为具身智能体的世界模拟器', s: 'We use VLM-generated latent world states to train embodied agents, improving zero-shot navigation success by 30% in unseen indoor environments.', tags: ['Embodied AI', 'VLM', 'World Model'] },
  { t: 'Quantization-Aware Training for 1.58-Bit Models at Scale', c: '1.58 位模型的量化感知训练实践', s: 'We show ternary-weight models can reach parity with FP16 at 1/8 the memory by training with stochastic ternary rounding, verified up to 70B parameters.', tags: ['Quantization', 'Efficiency', 'LLM'] },
  { t: 'Neural Causal Discovery with LLM Priors in Scientific Domains', c: '引入大模型先验的神经因果发现', s: 'LLM-generated causal priors combined with constraint-based discovery outperform purely data-driven methods on 12 scientific datasets, with open benchmarks.', tags: ['Causal Inference', 'LLM', 'Science'] },
  { t: 'Adaptive Retrieval Scheduling for 24/7 Research Monitoring Agents', c: '面向全天候研究监控智能体的自适应检索调度', s: 'We propose a cost-aware scheduler that decides when to query each source, cutting API spend 63% while keeping recall above 95% for overnight monitoring tasks.', tags: ['Agent', 'Retrieval', 'Monitoring'] },
  { t: 'Contrastive Preference Optimization for Multilingual Reasoning', c: '面向多语言推理的对比偏好优化', s: 'CPO aligns reasoning traces across 40 languages by contrasting monolingual and translated preference pairs, lifting MGSM accuracy on low-resource languages by 19%.', tags: ['NLP', 'Multilingual', 'Alignment'] },
  { t: 'World Model Distillation for Video Generation at 4K Resolution', c: '用于 4K 视频生成的世界模型蒸馏', s: 'Distilling a latent world model into a sparse diffusion transformer enables 4K, 30s video generation on a single A100, with temporal consistency metrics on par with 8x-cost models.', tags: ['Video Generation', 'Diffusion', 'Multimodal'] },
  { t: 'Formal Verification of RLHF Reward Models', c: 'RLHF 奖励模型的正式验证框架', s: 'We adapt model checking to neural reward functions, automatically detecting reward hacking configurations before deployment — tested on three production reward models.', tags: ['RLHF', 'Safety', 'Formal Methods'] },
  { t: 'On-Policy Data Mixing for Stable Long-Horizon Agent Training', c: '长程智能体训练的在线数据混合策略', s: 'A curriculum over on-policy rollouts that prevents representation collapse in long-horizon agent training, improving task success 24% over static replay.', tags: ['Agent', 'RL', 'Curriculum'] },
]

const rssTitles = [
  '机器之心：开源社区发布 70B 推理模型，多项基准逼近闭源旗舰',
  '量子位：AI 编程助手代码评审准确率首次超越资深工程师',
  '新智元：国内首个金融大模型通过备案，聚焦风控与投研场景',
  '机器之心：斯坦福新研究揭示 RLHF 后的奖励过拟合风险',
  '极客公园：端侧小模型 2026 全景报告：手机厂商的 AI 竞赛',
  '机器之心：Meta 开源 3D 生成模型，单卡 10 秒生成可编辑网格',
  '量子位：人形机器人成本降至 10 万元，量产元年开启',
  '机器之心：多模态大模型在医学影像诊断上的首个大规模随机试验',
  '新智元：向量数据库选型指南：Chroma 之外还有什么？',
  '极客公园：从 Demo 到生产：Agent 应用落地的 12 个坑',
  '机器之心：图神经网络 + 大模型：蛋白质设计迎来新范式',
  '量子位：100 行代码实现 RAG 应用：框架的终结还是开始？',
]

const rssSummary = [
  '本文系统梳理了本周 AI 领域的重要动态，并邀请多位一线研究员进行解读。',
  '该模型在多项权威评测中表现亮眼，社区已开放权重与推理脚本。',
  '业内人士指出，这一进展意味着相关技术正从实验室走向规模化商用。',
  '文章从技术原理、工程实现与商业化路径三个维度进行了深度拆解。',
  '多位开发者分享了实测数据与避坑经验，评论区讨论热度持续攀升。',
]

const tagPools: Record<SourceName, string[]> = {
  hackernews: ['LLM', 'Agent', 'Inference', 'Open Source', 'Startup', 'WebGPU', 'RAG', 'Tool Use', 'Benchmark', 'Serving', 'Multimodal'],
  arxiv: ['LLM', 'CV', 'NLP', 'RL', 'Multimodal', 'Embodied AI', 'Efficiency', 'Interpretability', 'Safety', 'Reasoning', 'Scaling'],
  huggingface_papers: ['LLM', 'Diffusion', 'RAG', 'Audio', 'Inference', 'Serving', 'Fine-Tuning', 'Dataset', 'Multimodal', 'Alignment'],
  rss: ['大模型', '多模态', '具身智能', 'AI 应用', '行业动态', '开源', '芯片', '安全'],
}

/* ---------- 确定性伪随机（mulberry32） ---------- */
let seedCounter = 1
function rng(): number {
  let t = (seedCounter += 0x6d2b79f5)
  t = Math.imul(t ^ (t >>> 15), t | 1)
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}
function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(rng() * arr.length)]
}
function range(lo: number, hi: number): number {
  return lo + rng() * (hi - lo)
}

/* ---------- 生成式文章组装 ---------- */
const generatedArticles: Article[] = []
const sourceOrder: SourceName[] = ['hackernews', 'arxiv', 'huggingface_papers', 'rss']
const DAY_MS = 24 * 60 * 60 * 1000
const anchor = Date.parse(MOCK_NOW)
const fromUtc = (iso: string) => Date.parse(iso)
let genSeq = 0

// 每个源每日 1–2 篇，覆盖近 14 天
for (let day = 13; day >= 0; day--) {
  const dayStart = anchor - day * DAY_MS
  for (const source of sourceOrder) {
    const count = day === 0 ? 2 : Math.floor(range(1, 2.9))
    for (let i = 0; i < count; i++) {
      const topic = pick(topicPool)
      const hour = Math.floor(range(6, 22))
      const minute = Math.floor(range(0, 59))
      const published = new Date(dayStart + hour * 3600_000 + minute * 60_000)
      const isZh = source === 'rss'
      const title = isZh ? pick(rssTitles) : topic.t
      const summary = isZh
        ? pick(rssSummary)
        : `${topic.s} (Generated demo article from the ${topic.tags[0]} track.)`
      const base = 15 + rng() * 500
      const recentBoost = day <= 2 ? 1.35 : day <= 6 ? 1.15 : 1
      genSeq += 1
      generatedArticles.push({
        id: `${source}:gen-${String(genSeq).padStart(4, '0')}`,
        title,
        url:
          source === 'hackernews'
            ? `https://news.ycombinator.com/item?id=${38000000 + genSeq}`
            : source === 'arxiv'
              ? `https://arxiv.org/abs/2608.${String(10000 + genSeq).padStart(5, '0')}`
              : source === 'huggingface_papers'
                ? `https://huggingface.co/papers/2608.${String(20000 + genSeq).padStart(5, '0')}`
                : `https://www.jiqizhixin.com/articles/2026-08-${String(18 - day).padStart(2, '0')}-${String(genSeq).padStart(2, '0')}`,
        source,
        summary,
        author: isZh ? pick(['机器之心', '量子位', '新智元', '极客公园']) : null,
        published_at: published.toISOString(),
        score: Math.floor(base * recentBoost),
        tags: isZh
          ? [...new Set([pick(tagPools.rss), pick(tagPools.rss), pick(tagPools.rss)])].slice(0, 3)
          : [...new Set([topic.tags[0], pick(tagPools[source]), pick(tagPools[source])])].slice(0, 3),
        language: isZh ? 'zh' : 'en',
      })
    }
  }
}

export const mockArticles: Article[] = [...seedArticles, ...generatedArticles].sort(
  (a, b) => fromUtc(b.published_at ?? '') - fromUtc(a.published_at ?? ''),
)

/* ---------- Agent 对话（对应 POST /api/agent/chat） ---------- */
export const WELCOME_MESSAGE: ChatMessage = {
  role: 'assistant',
  content:
    '**AGENT TERMINAL ONLINE**\n\n我是你的 AI 研究情报助手，可以检索资料库、解读论文、分析趋势或触发数据采集。\n\n试试下方的快捷操作，或直接输入问题——例如：\n\n> 总结一下最近 3 天 Hacker News 上关于 Agent 的讨论\n\n*HISTORY: 0/20 ROUNDS*',
  timestamp: '2026-08-18T09:30:00+08:00',
}

export const mockInitialMessages: ChatMessage[] = [WELCOME_MESSAGE]

export const mockHistory: ChatMessage[] = [
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

export const QUICK_ACTIONS: Array<{ key: string; prompt: string }> = [
  { key: 'todaySummary', prompt: '总结今天的 AI 热点' },
  { key: 'researchTrends', prompt: '分析最近的研究趋势' },
  { key: 'recommendPapers', prompt: '推荐值得阅读的论文' },
  { key: 'triggerCollect', prompt: '立即触发一次数据采集' },
]

export const MOCK_MAX_CHARS = 4000
export const MOCK_MAX_HISTORY = 20

/** 校验最后一个启用源：全部禁用时返回警告文案（对应后端 400） */
export function validateLastSource(sources: Source[]): string | null {
  if (sources.every((s) => !s.enabled)) {
    return '至少保留一个启用的信息源（对应后端 400：ALL_SOURCES_DISABLED）'
  }
  return null
}
