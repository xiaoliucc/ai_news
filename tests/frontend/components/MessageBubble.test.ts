// @vitest-environment jsdom
/**
 * MessageBubble 渲染安全回归测试（体检报告 H-6-1）。
 *
 * 背景：Agent 回答经 marked 转 HTML 后走 v-html 渲染，而回答里会引用采集到的
 * 外部标题/摘要。marked 不做安全过滤，因此渲染前必须过 DOMPurify——这组用例
 * 锁住"危险标签/属性被剥离、正常 Markdown 结构保留"这条契约。
 *
 * 环境说明：本文件固定用 jsdom（项目其余测试是 happy-dom）。happy-dom 的 DOM
 * 遍历与 DOMPurify 3.x 不兼容（实测 sanitize 会漏掉 <script> 却误删 <a>/<ul>），
 * 在该环境下测消毒只会得到假结论。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '@/components/MessageBubble.vue'
import type { ChatMessage } from '@/types'

function assistant(content: string): ChatMessage {
  return { role: 'assistant', content, timestamp: new Date().toISOString() }
}

function render(content: string): string {
  const wrapper = mount(MessageBubble, { props: { message: assistant(content) } })
  return wrapper.find('.bubble__content').html()
}

describe('MessageBubble 消毒', () => {
  it('剥离 <script> 标签及其内容', () => {
    const html = render('正常文本<script>alert(1)</script>')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('alert(1)')
    expect(html).toContain('正常文本')
  })

  it('剥离事件属性与不在白名单的 <img>', () => {
    const html = render('<img src=x onerror="alert(1)">')
    expect(html).not.toContain('onerror')
    expect(html).not.toContain('<img')
  })

  it('剥离开头 javascript: 的链接地址', () => {
    const html = render('[点我](javascript:alert(1))')
    expect(html.toLowerCase()).not.toContain('javascript:')
    expect(html).toContain('点我')
  })

  it('剥离 onclick / style，保留文字与合法 href', () => {
    const html = render('<a href="https://example.com" onclick="alert(1)" style="color:red">链接</a>')
    expect(html).not.toContain('onclick')
    expect(html).not.toContain('style=')
    expect(html).toContain('href="https://example.com"')
    expect(html).toContain('链接')
  })
})

describe('MessageBubble 正常渲染不回归', () => {
  it('保留粗体与行内代码', () => {
    const html = render('**重点** 与 `code`')
    expect(html).toContain('<strong>重点</strong>')
    expect(html).toContain('<code>code</code>')
  })

  it('保留列表结构', () => {
    const html = render('- 一\n- 二')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>一</li>')
  })

  it('外链补 target=_blank 与 rel=noopener noreferrer', () => {
    const html = render('[示例](https://example.com)')
    expect(html).toContain('href="https://example.com"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('noopener')
    expect(html).toContain('noreferrer')
  })

  it('流式增量文本优先于 message.content', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: assistant('旧的完整回答'), streamingText: '新的增量' },
    })
    const html = wrapper.find('.bubble__content').html()
    expect(html).toContain('新的增量')
    expect(html).not.toContain('旧的完整回答')
  })
})
