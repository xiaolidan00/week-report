<script setup lang="ts">
  import {computed, ref} from "vue";
  import {dayjs, ElMessage} from "element-plus";
  import {Calendar, Refresh, Document} from "@element-plus/icons-vue";
  import {gitLog} from "@/api";
  import type {GitCommit} from "@/types/api";
  import {useProjectStore} from "@/stores/project";
  import {useChatStore} from "@/stores/chat";

  const projectStore = useProjectStore();
  const chatStore = useChatStore();

  const range = ref<[string, string] | null>(null);
  const previewing = ref(false);
  const generating = ref(false);
  const previewOpen = ref(false);
  const previewCommits = ref<GitCommit[]>([]);
  const previewTotal = ref(0);

  const since = computed(() => range.value?.[0] ?? null);
  const until = computed(() => range.value?.[1] ?? null);

  /** 当前对话所属项目（无对话时为 null） */
  const activeProject = computed(() => {
    const chat = chatStore.activeChat;
    if (!chat) return null;
    return projectStore.projects.find((p) => p.id === chat.project_id) ?? null;
  });

  async function fetchPreview() {
    if (!activeProject.value) {
      ElMessage.warning("请先在左侧选择一个对话");
      return;
    }
    if (!range.value || !range.value[0] || !range.value[1]) {
      ElMessage.warning("请先选择时间范围");
      return;
    }
    previewing.value = true;
    try {
      const result = await gitLog(activeProject.value.id, since.value, until.value);
      previewCommits.value = result.commits;
      previewTotal.value = result.total;
      previewOpen.value = true;
      if (result.total === 0) ElMessage.warning("该时间范围内没有提交记录");
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e));
    } finally {
      previewing.value = false;
    }
  }

  async function generateReport() {
    if (!chatStore.activeChatId) {
      ElMessage.warning("请先在左侧创建或选择一个对话");
      return;
    }
    if (!range.value || !range.value[0] || !range.value[1]) {
      ElMessage.warning("请先选择时间范围");
      return;
    }
    const draft = chatStore.draft.trim();
    const timestr = `【${dayjs(range.value[0]).format("YYYY-MM-DD")}~${dayjs(range.value[1]).format("YYYY-MM-DD")}】`;
    const content = draft
      ? `请结合${timestr}时间范围内的 git 提交记录回答。\n\n${draft}`
      : `请根据${timestr}时间范围内的 git 提交记录，生成本周工作周报。`;
    chatStore.draft = "";
    generating.value = true;
    try {
      await chatStore.send(content, {since: since.value, until: until.value, generate: true});
    } finally {
      generating.value = false;
    }
  }
</script>

<template>
  <div class="time-range-bar">
    <el-date-picker
      v-model="range"
      type="daterange"
      range-separator="~"
      start-placeholder="开始日期"
      end-placeholder="结束日期"
      value-format="YYYY-MM-DD"
      :clearable="true"
      size="default"
      style="width: 260px"
    />

    <el-button :icon="Refresh" :loading="previewing" @click="fetchPreview">查询提交</el-button>

    <el-button
      type="primary"
      :icon="Document"
      :loading="generating || chatStore.sending"
      :disabled="!chatStore.activeChatId"
      @click="generateReport"
    >
      生成周报
    </el-button>

    <span v-if="previewTotal > 0" class="preview-count">
      <el-icon><Calendar /></el-icon>
      范围内 {{ previewTotal }} 次提交
    </span>

    <el-dialog v-model="previewOpen" title="时间范围内提交记录" width="720px" align-center>
      <div class="commit-list">
        <div v-for="c in previewCommits" :key="c.sha" class="commit-item">
          <span class="commit-date">{{ c.date }}</span>
          <span class="commit-sha">{{ c.short_sha }}</span>
          <span class="commit-subject">{{ c.subject }}</span>
          <span class="commit-author">{{ c.author }}</span>
        </div>
        <el-empty v-if="previewCommits.length === 0" description="无提交记录" :image-size="64" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
  .time-range-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .preview-count {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .commit-list {
    max-height: 460px;
    overflow: auto;
  }
  .commit-item {
    display: flex;
    gap: 10px;
    align-items: baseline;
    padding: 6px 4px;
    border-bottom: 1px dashed var(--el-border-color-lighter);
    font-size: 13px;
  }
  .commit-date {
    flex: 0 0 84px;
    color: var(--el-text-color-secondary);
  }
  .commit-sha {
    flex: 0 0 72px;
    font-family: Consolas, monospace;
    color: var(--el-color-success);
  }
  .commit-subject {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .commit-author {
    flex: 0 0 auto;
    color: var(--el-text-color-secondary);
  }
</style>
