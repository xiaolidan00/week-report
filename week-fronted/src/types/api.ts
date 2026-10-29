/** 后端数据模型 */

export interface Project {
  id: number
  name: string
  path: string
  created_at: string
}

export interface Chat {
  id: number
  project_id: number
  title: string
  created_at: string
}

export interface Message {
  id: number
  chat_id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  /** 前端本地扩展：流式进行中标记 */
  streaming?: boolean
  /** 前端本地扩展：错误标记 */
  error?: boolean
}

export interface GitCommit {
  sha: string
  short_sha: string
  date: string
  author: string
  subject: string
  body: string
}

export interface GitLogResult {
  commits: GitCommit[]
  total: number
}

export interface HealthResult {
  chat: boolean
  embed: boolean
}

/** SSE 下行事件 */
export interface SSEMeta {
  commits: number
  rag: boolean
  project: string
  since?: string | null
  until?: string | null
  generate: boolean
}

export interface SSEEvent {
  meta?: SSEMeta
  token?: string
  done?: boolean
  id?: number
  /** 首条消息回答成功后的自动重命名标题（其余情况为 null） */
  title?: string | null
  /** 用户点击暂停：撤回刚发送的问题 */
  stopped?: boolean
  /** 暂停时被撤回的问题原文 */
  question?: string
  error?: string
}

export interface ChatRequestBody {
  content: string
  since?: string | null
  until?: string | null
  generate?: boolean
}
