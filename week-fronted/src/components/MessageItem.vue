<script setup lang="ts">
  import {computed} from "vue";
  import {ElMessage} from "element-plus";
  import {CopyDocument, VideoPause, User, ChatDotRound} from "@element-plus/icons-vue";
  import MarkdownView from "./MarkdownView.vue";
  import {useChatStore} from "@/stores/chat";
  import type {Message} from "@/types/api";

  const props = defineProps<{message: Message}>();
  const chatStore = useChatStore();

  const isUser = computed(() => props.message.role === "user");
  /** 助手正在思考/流式输出中 */
  const isStreaming = computed(() => !isUser.value && !!props.message.streaming);

  async function copyContent() {
    try {
      await navigator.clipboard.writeText(props.message.content);
      ElMessage.success("已复制到剪贴板");
    } catch {
      ElMessage.error("复制失败");
    }
  }

  async function pause() {
    await chatStore.cancel();
  }
</script>

<template>
  <div class="message-item" :class="isUser ? 'is-user' : 'is-assistant'">
    <div class="avatar">
      <el-icon v-if="isUser"><User /></el-icon>
      <el-icon v-else><ChatDotRound /></el-icon>
    </div>

    <div class="bubble">
      <div class="bubble-header">
        <span class="role">{{ isUser ? "我" : "AI 周报助手" }}</span>
        <span class="time">{{ message.created_at }}</span>
        <el-button v-if="isStreaming" class="cancel-btn" type="danger" @click="pause"> 取消思考 </el-button>
        <el-button
          v-if="!isUser && message.content && !isStreaming"
          class="copy-btn"
          text
          size="small"
          :icon="CopyDocument"
          @click="copyContent"
        >
          复制
        </el-button>
      </div>

      <div v-if="isUser" class="user-content">{{ message.content }}</div>
      <div v-else class="assistant-content">
        <div v-if="isStreaming && !message.content" class="typing"><span></span><span></span><span></span></div>
        <MarkdownView v-else :content="message.content" />
      </div>
    </div>
  </div>
</template>

<style scoped>
  .message-item {
    display: flex;
    gap: 10px;
    padding: 10px 4px;
  }
  .message-item.is-user {
    flex-direction: row-reverse;
  }

  .avatar {
    flex: 0 0 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 16px;
  }
  .is-user .avatar {
    background: var(--el-color-primary);
  }
  .is-assistant .avatar {
    background: #6b7b8c;
  }

  .bubble {
    max-width: calc(100% - 48px);
    min-width: 0;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 8px;
    padding: 8px 12px;
    background: var(--el-bg-color);
  }
  .is-user .bubble {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary-light-7);
  }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .bubble-header .role {
    font-weight: 600;
    color: var(--el-text-color-regular);
  }
  .copy-btn {
    margin-left: auto;
    padding: 4px;
  }
  .pause-btn {
    margin-left: auto;
    padding: 4px;
  }

  .user-content {
    white-space: pre-wrap;
    font-size: 14px;
    line-height: 1.7;
  }

  .typing {
    display: inline-flex;
    gap: 5px;
    padding: 6px 2px;
  }
  .typing span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--el-color-primary);
    animation: blink 1.2s infinite ease-in-out;
  }
  .typing span:nth-child(2) {
    animation-delay: 0.2s;
  }
  .typing span:nth-child(3) {
    animation-delay: 0.4s;
  }
  @keyframes blink {
    0%,
    80%,
    100% {
      opacity: 0.25;
      transform: scale(0.85);
    }
    40% {
      opacity: 1;
      transform: scale(1);
    }
  }
</style>
