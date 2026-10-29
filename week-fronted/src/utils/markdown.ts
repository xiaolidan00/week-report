import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkRehype from 'remark-rehype'
import rehypeHighlight from 'rehype-highlight'
import rehypeMermaid from 'rehype-mermaid'
import rehypeStringify from 'rehype-stringify'

/** README 规定的 markdown 解析管线：mdast -> gfm -> mermaid inline-svg -> 高亮 -> html */
export const getMarkdownParse = () => {
  const parser = unified()
    .use(remarkParse) // markdown -> mdast
    .use(remarkGfm)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeMermaid, {
      strategy: 'inline-svg',
    })
    .use(rehypeHighlight)
    .use(rehypeStringify, { allowDangerousHtml: true })
  return parser
}

/** 降级管线：不渲染 mermaid（流式输出中 mermaid 代码块不完整时使用） */
const getPlainParse = () =>
  unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeHighlight)
    .use(rehypeStringify, { allowDangerousHtml: true })

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')

/**
 * 渲染 markdown 为 HTML 字符串。
 * 1) 完整管线（含 mermaid）失败时降级为无 mermaid 管线；
 * 2) 仍失败则转义为纯文本，保证流式输出不中断。
 */
export async function renderMarkdown(markdown: string): Promise<string> {
  if (!markdown) return ''
  try {
    return String(await getMarkdownParse().process(markdown))
  } catch {
    try {
      return String(await getPlainParse().process(markdown))
    } catch {
      return escapeHtml(markdown)
    }
  }
}
