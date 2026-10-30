<script setup lang="ts">
  import {onBeforeUnmount, onMounted} from "vue";
  import {ElNotification} from "element-plus";
  import ProjectTree from "@/components/ProjectTree.vue";
  import ChatPanel from "@/components/ChatPanel.vue";
  import {useProjectStore} from "@/stores/project";
  import {useChatStore} from "@/stores/chat";
  import {health} from "@/api";

  const projectStore = useProjectStore();
  const chatStore = useChatStore();

  onMounted(async () => {
    // 1. 拉取项目/对话数据（后端未启动时给出明确提示）
    try {
      await Promise.all([projectStore.fetch(), chatStore.fetchChats()]);
    } catch (e) {
      ElNotification.error({
        title: "后端服务未连接",
        message: e instanceof Error ? e.message : String(e),
        duration: 8000
      });
    }
    // 2. 检查本地模型服务
    try {
      const h = await health();
      if (!h.chat) {
        ElNotification.warning({
          title: "对话模型未启动",
          message: "请运行 backend\\start-llama.bat 启动 llama-server (8001)",
          duration: 10000
        });
      }
      if (!h.embed) {
        ElNotification.warning({
          title: "Embedding 模型未启动",
          message: "请运行 backend\\start-embed.bat 启动 embedding 服务 (8002)，否则将降级为 git 日志直读",
          duration: 10000
        });
      }
    } catch {
      /* health 失败已在上面提示 */
    }
  });
  onBeforeUnmount(() => {
    chatStore.cancel();
  });
</script>

<template>
  <el-container class="app-container">
    <el-aside width="272px" class="app-aside">
      <ProjectTree />
    </el-aside>
    <el-main class="app-main">
      <ChatPanel />
    </el-main>
  </el-container>
</template>

<style scoped>
  .app-container {
    height: 100vh;
  }
  .app-aside {
    border-right: 1px solid var(--el-border-color-lighter);
    background: var(--el-bg-color-page);
    overflow: hidden;
  }
  .app-main {
    padding: 0;
    overflow: hidden;
  }
</style>
