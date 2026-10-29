/** 极简 HTTP 封装：统一错误处理 + 后端未启动提示 */

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch {
    throw new ApiError('无法连接后端服务，请先启动 start-llama.bat / start-embed.bat / start-backend.bat', 0)
  }
  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`
    try {
      const data = await resp.json()
      if (data?.detail) detail = String(data.detail)
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status)
  }
  return (await resp.json()) as T
}
