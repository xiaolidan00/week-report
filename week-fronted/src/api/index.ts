/** 后端 REST / SSE 接口 */
import {request} from "./http";
import type {Chat, ChatRequestBody, GitLogResult, HealthResult, Message, Project, SSEEvent} from "@/types/api";

// ---------- projects ----------
export const listProjects = () => request<Project[]>("/api/projects");

export const createProject = (path: string) =>
  request<Project>("/api/projects", {method: "POST", body: JSON.stringify({path})});

export const deleteProject = (id: number) => request<{ok: boolean}>(`/api/projects/${id}`, {method: "DELETE"});

// ---------- chats ----------
export const listChats = (projectId?: number) =>
  request<Chat[]>(projectId ? `/api/chats?project_id=${projectId}` : "/api/chats");

export const createChat = (projectId: number, title?: string) =>
  request<Chat>("/api/chats", {
    method: "POST",
    body: JSON.stringify({project_id: projectId, title})
  });

export const deleteChat = (id: number) => request<{ok: boolean}>(`/api/chats/${id}`, {method: "DELETE"});

export const listMessages = (chatId: number) => request<Message[]>(`/api/chats/${chatId}/messages`);

export const stopGeneration = (chatId: number, signal: any) =>
  request<{ok: boolean}>(`/api/chats/${chatId}/stop`, {method: "POST", signal});

// ---------- git / health ----------
export const gitLog = (projectId: number, since?: string | null, until?: string | null) => {
  const params = new URLSearchParams({project_id: String(projectId)});
  if (since) params.set("since", since);
  if (until) params.set("until", until);
  return request<GitLogResult>(`/api/git/log?${params}`);
};

export const health = () => request<HealthResult>("/api/health");

// ---------- SSE 流式对话 ----------
export async function streamChat(
  chatId: number,
  body: ChatRequestBody,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(`/api/chats/${chatId}/messages`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
      signal
    });
  } catch {
    throw new Error("无法连接后端服务，请确认 start-backend.bat 已启动");
  }
  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败 (${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const dispatch = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) return;
    const json = trimmed.slice(5).trim();
    if (!json) return;
    try {
      onEvent(JSON.parse(json) as SSEEvent);
    } catch {
      /* 跳过无法解析的片段 */
    }
  };

  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      for (const line of chunk.split("\n")) {
        dispatch(line);
      }
    }
  }
  if (buffer.trim()) {
    for (const line of buffer.split("\n")) dispatch(line);
  }
}
