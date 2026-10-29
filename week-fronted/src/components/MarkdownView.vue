<script setup lang="ts">
import { ref, watch } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ content: string }>()

const html = ref('')
let timer: number | null = null
let seq = 0

async function render() {
  const current = ++seq
  const result = await renderMarkdown(props.content)
  if (current === seq) html.value = result
}

watch(
  () => props.content,
  () => {
    if (timer !== null) window.clearTimeout(timer)
    // 流式输出时节流渲染，避免每个 token 触发一次 mermaid 解析
    timer = window.setTimeout(() => {
      timer = null
      render()
    }, 120)
  },
  { immediate: true },
)
</script>

<template>
  <div class="markdown-view markdown-body" v-html="html"></div>
</template>

<style scoped>
.markdown-view {
  word-break: break-word;
}
</style>
