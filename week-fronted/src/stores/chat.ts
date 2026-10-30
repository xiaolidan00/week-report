import {defineStore} from "pinia";
import * as api from "@/api";
import type {Chat, Message, SSEMeta} from "@/types/api";

/** 本地生成的临时 id（远端落库后会替换为真实 id） */
const tempId = () => -Date.now() - Math.floor(Math.random() * 1000);

const nowStr = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};

interface ChatState {
  chats: Chat[];
  activeChatId: number | null;
  messages: Message[];
  sending: boolean;
  /** 最近一次生成的上下文元信息（检索条数 / 是否 RAG） */
  meta: SSEMeta | null;
  loadingMessages: boolean;
  /** 输入框草稿（生成周报时作为附加问题） */
  draft: string;
}

export const useChatStore = defineStore("chat", {
  state: (): ChatState => ({
    chats: [],
    activeChatId: null,
    messages: [],
    sending: false,
    meta: null,
    loadingMessages: false,
    draft: ""
  }),
  getters: {
    activeChat(state): Chat | null {
      return state.chats.find((c) => c.id === state.activeChatId) ?? null;
    },
    chatsByProject(state): (projectId: number) => Chat[] {
      return (projectId: number) => state.chats.filter((c) => c.project_id === projectId);
    }
  },
  actions: {
    async fetchChats() {
      this.chats = await api.listChats();
    },
    async createChat(projectId: number, title?: string) {
      const chat = await api.createChat(projectId, title);
      this.chats.push(chat);
      return chat;
    },
    async removeChat(chatId: number) {
      await api.deleteChat(chatId);
      this.chats = this.chats.filter((c) => c.id !== chatId);
      if (this.activeChatId === chatId) {
        this.activeChatId = null;
        this.messages = [];
        this.meta = null;
      }
    },
    async selectChat(chatId: number) {
      if (this.activeChatId === chatId) return;
      this.activeChatId = chatId;
      this.meta = null;
      this.loadingMessages = true;
      try {
        this.messages = await api.listMessages(chatId);
      } finally {
        this.loadingMessages = false;
      }
    },
    clearActive() {
      this.activeChatId = null;
      this.messages = [];
      this.meta = null;
    },

    /** 流式发送（SSE），返回是否成功完成 */
    async send(
      content: string,
      opts: {since?: string | null; until?: string | null; generate?: boolean} = {}
    ): Promise<boolean> {
      const chatId = this.activeChatId;
      if (!chatId) throw new Error("请先在左侧创建或选择一个对话");
      if (this.sending) throw new Error("正在生成中，请稍候");

      const stamp = nowStr();
      const userMsg: Message = {
        id: tempId(),
        chat_id: chatId,
        role: "user",
        content,
        created_at: stamp
      };
      const assistantMsg: Message = {
        id: tempId(),
        chat_id: chatId,
        role: "assistant",
        content: "",
        created_at: stamp,
        streaming: true
      };
      this.messages.push(userMsg, assistantMsg);
      this.sending = true;
      let ok = false;
      let stopped = false;

      try {
        await api.streamChat(chatId, {content, since: opts.since, until: opts.until, generate: opts.generate}, (ev) => {
          if (ev.meta) this.meta = ev.meta;
          if (ev.token) assistantMsg.content += ev.token;
          if (ev.error) {
            assistantMsg.error = true;
            assistantMsg.content = assistantMsg.content
              ? `${assistantMsg.content}\n\n> ⚠️ ${ev.error}`
              : `> ⚠️ ${ev.error}`;
          }
          if (ev.done) {
            ok = true;
            if (ev.id) assistantMsg.id = ev.id;
            // 首条消息自动重命名：同步对话标题（项目树/顶栏即时更新）
            if (ev.title) {
              const chat = this.chats.find((c) => c.id === chatId);
              if (chat) chat.title = ev.title;
            }
          }
          if (ev.stopped) stopped = true;
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        assistantMsg.error = true;
        assistantMsg.content = assistantMsg.content ? `${assistantMsg.content}\n\n> ⚠️ ${msg}` : `> ⚠️ ${msg}`;
      } finally {
        assistantMsg.streaming = false;
        this.sending = false;
        // 暂停：移除本地的用户问题与（空的）助手消息，并把问题撤回到输入框
        if (stopped) {
          this.messages = this.messages.filter((m) => m.id !== userMsg.id && m.id !== assistantMsg.id);
          if (!this.draft) this.draft = content;
        }
      }
      return ok;
    },

    /** 取消当前对话正在进行的思考：通知后端停止生成并撤回刚发送的问题 */
    async cancel() {
      if (!this.sending || !this.activeChatId) return;

      try {
        // 1. 停止 SSE 流
        const abortController = new AbortController();
        const signal = abortController.signal;
        await api.stopGeneration(this.activeChatId, signal);

        // 2. 从本地消息数组中移除用户消息和助手消息
        let question = "";
        if (this.messages.at(-1)?.role === "assistant") this.messages.pop();
        if (this.messages.at(-1)?.role === "user") {
          question = this.messages.at(-1)!.content;
          this.messages.pop();
        }

        // 3. 恢复用户问题到输入框
        if (!this.draft) this.draft = question;
        this.sending = false;
      } catch {
        /* 后端不可达时忽略，流会以错误结束 */
      }
    }
  }
});
