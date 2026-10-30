<script setup lang="ts">
  import {computed, nextTick, ref, watch} from "vue";
  import {ElMessage} from "element-plus";
  import {Promotion, FolderOpened} from "@element-plus/icons-vue";
  import TimeRangeBar from "./TimeRangeBar.vue";
  import MessageItem from "./MessageItem.vue";
  import {useChatStore} from "@/stores/chat";
  import {useProjectStore} from "@/stores/project";

  const chatStore = useChatStore();
  const projectStore = useProjectStore();

  const listRef = ref<HTMLElement | null>(null);
  const inputRef = ref();
  const stickBottom = ref(true);

  /** 问题目录项（仅用户消息） */
  interface QuestionItem {
    id: number;
    text: string;
    time: string;
  }

  const catalogOpen = ref(true);
  /** 目录中当前高亮项（对应消息列表滚动位置），-1 表示未选中 */
  const activeQuestionIdx = ref(-1);
  /** 点击目录后短暂高亮的目标消息 id */
  const flashMid = ref<number | null>(null);
  let flashTimer: number | undefined;

  const questions = computed<QuestionItem[]>(() =>
    chatStore.messages
      .filter((m) => m.role === "user")
      .map((m) => ({id: m.id, text: m.content.trim(), time: m.created_at}))
  );

  const activeProject = computed(() => {
    const chat = chatStore.activeChat;
    if (!chat) return null;
    return projectStore.projects.find((p) => p.id === chat.project_id) ?? null;
  });

  const metaText = computed(() => {
    const meta = chatStore.meta;
    if (!meta) return "";
    const parts = [`项目 ${meta.project}`];
    if (meta.since || meta.until) parts.push(`范围 ${meta.since || "不限"} ~ ${meta.until || "不限"}`);
    parts.push(`上下文 ${meta.commits} 条`);
    parts.push(meta.rag ? "RAG 向量检索" : meta.commits > 0 ? "git 日志直读" : "无提交上下文");
    return parts.join(" · ");
  });

  function scrollToBottom(smooth = false) {
    const el = listRef.value;
    if (!el) return;
    el.scrollTo({top: el.scrollHeight, behavior: smooth ? "smooth" : "auto"});
  }

  function onScroll() {
    const el = listRef.value;
    if (!el) return;
    stickBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    updateActiveQuestion();
  }

  /** 根据滚动位置同步目录高亮项（最后一条顶部在视口上方的问题） */
  function updateActiveQuestion() {
    const container = listRef.value;
    if (!container || questions.value.length === 0) {
      activeQuestionIdx.value = -1;
      return;
    }
    const containerTop = container.getBoundingClientRect().top;
    let current = -1;
    questions.value.forEach((q, i) => {
      const dom = container.querySelector<HTMLElement>(`[data-mid="${q.id}"]`);
      if (dom && dom.getBoundingClientRect().top - containerTop <= 60) current = i;
    });
    activeQuestionIdx.value = current;
  }

  /** 点击目录项：滚动定位到对应消息并短暂高亮 */
  function jumpToQuestion(q: QuestionItem, idx: number) {
    activeQuestionIdx.value = idx;
    stickBottom.value = false;
    flashMid.value = q.id;
    window.clearTimeout(flashTimer);
    flashTimer = window.setTimeout(() => (flashMid.value = null), 1300);
    nextTick(() => {
      const dom = listRef.value?.querySelector<HTMLElement>(`[data-mid="${q.id}"]`);
      dom?.scrollIntoView({behavior: "smooth", block: "start"});
    });
  }

  /** 目录高亮项变化时让目录自身滚动到可见区域 */
  watch(activeQuestionIdx, async (idx) => {
    if (idx < 0 || !catalogOpen.value) return;
    await nextTick();
    document.querySelector(".catalog-item.active")?.scrollIntoView({block: "nearest"});
  });

  /** 消息内容增长（流式）时跟随滚动 */
  const contentSignature = computed(() => chatStore.messages.map((m) => m.content.length).join(","));
  watch(contentSignature, async () => {
    if (!stickBottom.value) return;
    await nextTick();
    scrollToBottom();
  });

  /** 切换对话时重置并滚到底 */
  watch(
    () => chatStore.activeChatId,
    async () => {
      stickBottom.value = true;
      activeQuestionIdx.value = -1;
      flashMid.value = null;
      await nextTick();
      scrollToBottom();
      updateActiveQuestion();
      if (chatStore.activeChatId) inputRef.value?.focus?.();
    }
  );

  async function send() {
    const content = chatStore.draft.trim();
    if (!content) return;
    if (!chatStore.activeChatId) {
      ElMessage.warning("请先在左侧创建或选择一个对话");
      return;
    }
    chatStore.draft = "";
    stickBottom.value = true;
    await chatStore.send(content);
    await nextTick();
    scrollToBottom();
    updateActiveQuestion();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key !== "Enter" || e.isComposing) return;
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const el = e.target as HTMLTextAreaElement;
      const start = el.selectionStart;
      const end = el.selectionEnd;
      chatStore.draft = chatStore.draft.slice(0, start) + "\n" + chatStore.draft.slice(end);
      nextTick(() => {
        el.selectionStart = el.selectionEnd = start + 1;
      });
    } else if (!e.shiftKey && !e.altKey) {
      e.preventDefault();
      send();
    }
  }
</script>

<template>
  <div class="chat-panel">
    <!-- 顶部：对话标题 + 时间范围操作 -->
    <div class="panel-header">
      <div class="header-title">
        <span class="chat-title">{{ chatStore.activeChat?.title || "周报对话" }}</span>
        <span v-if="activeProject" class="project-path" :title="activeProject.path">
          <el-icon><FolderOpened /></el-icon>
          {{ activeProject.path }}
        </span>
      </div>
      <TimeRangeBar v-if="chatStore.activeChatId" />
    </div>

    <!-- 上下文信息条 -->
    <div v-if="metaText" class="meta-bar">{{ metaText }}</div>

    <!-- 消息区：消息列表 + 右侧问题目录 -->
    <div class="chat-body">
      <div ref="listRef" class="message-list" v-loading="chatStore.loadingMessages" @scroll="onScroll">
        <template v-if="chatStore.activeChatId">
          <el-empty
            v-if="chatStore.messages.length === 0"
            description="开始对话吧：直接输入问题，或选择时间范围后点击「生成周报」"
            :image-size="80"
          />
          <MessageItem
            v-for="(msg, index) in chatStore.messages"
            :key="msg.id ?? index"
            :message="msg"
            :data-mid="msg.id"
            :class="{flash: flashMid === msg.id}"
          />
        </template>
        <el-empty v-else description="请在左侧选择对话，或点击项目右侧 + 创建新对话" :image-size="90" />
      </div>

      <!-- 右侧问题目录 -->
      <aside v-if="catalogOpen" class="question-catalog">
        <div class="catalog-header">
          <span>问题目录</span>
          <span class="catalog-count">{{ questions.length }}</span>
          <el-button class="catalog-collapse" text size="small" @click="catalogOpen = false"> 收起 </el-button>
        </div>
        <div class="catalog-list">
          <el-empty v-if="questions.length === 0" description="暂无问题" :image-size="48" />
          <button
            v-for="(q, i) in questions"
            :key="q.id"
            class="catalog-item"
            :class="{active: activeQuestionIdx === i}"
            :title="`${q.text}\n${q.time}`"
            @click="jumpToQuestion(q, i)"
          >
            <span class="q-index">{{ i + 1 }}</span>
            <span class="q-text">{{ q.text }}</span>
          </button>
        </div>
      </aside>
      <button v-else class="catalog-toggle" title="展开问题目录" @click="catalogOpen = true">
        问题目录（{{ questions.length }}）
      </button>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <el-input
        ref="inputRef"
        v-model="chatStore.draft"
        type="textarea"
        :rows="3"
        resize="none"
        placeholder="输入问题，Enter 发送，Ctrl+Enter 换行；或选择时间范围后点「生成周报」"
        :disabled="!chatStore.activeChatId"
        @keydown="onKeydown"
      />
      <div class="input-actions">
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="chatStore.sending"
          :disabled="!chatStore.activeChatId"
          @click="send"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .chat-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
  }

  .panel-header {
    padding: 10px 16px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .header-title {
    display: flex;
    align-items: baseline;
    gap: 12px;
    min-width: 0;
  }
  .chat-title {
    font-weight: 600;
    font-size: 15px;
  }
  .project-path {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .meta-bar {
    padding: 5px 16px;
    font-size: 12px;
    color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
    border-bottom: 1px solid var(--el-color-primary-light-7);
  }

  .chat-body {
    flex: 1;
    display: flex;
    min-height: 0;
  }

  .message-list {
    flex: 1;
    overflow: auto;
    padding: 8px 16px;
    min-width: 0;
  }
  .streaming-flag {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    padding: 2px 4px 8px;
  }

  /* 点击目录定位后的短暂高亮 */
  @keyframes flash-bg {
    0%,
    60% {
      background: var(--el-color-primary-light-8);
    }
    100% {
      background: transparent;
    }
  }
  .message-list .flash {
    animation: flash-bg 1.3s ease;
    border-radius: 8px;
  }

  /* ===== 右侧问题目录 ===== */
  .question-catalog {
    flex: 0 0 220px;
    min-width: 0;
    border-left: 1px solid var(--el-border-color-lighter);
    background: var(--el-bg-color-page);
    display: flex;
    flex-direction: column;
  }
  .catalog-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 10px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    font-size: 13px;
    font-weight: 600;
  }
  .catalog-count {
    font-weight: 400;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .catalog-collapse {
    margin-left: auto;
  }
  .catalog-list {
    flex: 1;
    overflow: auto;
    padding: 6px;
  }
  .catalog-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    text-align: left;
    border: none;
    background: transparent;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    color: var(--el-text-color-regular);
  }
  .catalog-item:hover {
    background: var(--el-fill-color-light);
  }
  .catalog-item.active {
    background: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
  }
  .q-index {
    flex: 0 0 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--el-fill-color);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: var(--el-text-color-secondary);
  }
  .catalog-item.active .q-index {
    background: var(--el-color-primary);
    color: #fff;
  }
  .q-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    line-height: 18px;
  }

  /* 收起后的竖条 */
  .catalog-toggle {
    flex: 0 0 28px;
    border: none;
    border-left: 1px solid var(--el-border-color-lighter);
    background: var(--el-bg-color-page);
    cursor: pointer;
    writing-mode: vertical-rl;
    letter-spacing: 3px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    padding: 8px 0;
  }
  .catalog-toggle:hover {
    color: var(--el-color-primary);
  }

  .input-area {
    border-top: 1px solid var(--el-border-color-lighter);
    padding: 10px 16px;
    display: flex;
    gap: 10px;
    align-items: flex-end;
  }
  .input-area :deep(.el-textarea) {
    flex: 1;
  }
  .input-actions {
    display: flex;
    flex-direction: column;
  }
</style>
