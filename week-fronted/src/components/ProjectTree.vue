<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, FolderOpened, ChatLineRound } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useChatStore } from '@/stores/chat'

const projectStore = useProjectStore()
const chatStore = useChatStore()

/** 树节点：项目（父）-> 对话（子） */
interface TreeNode {
  key: string
  type: 'project' | 'chat'
  label: string
  projectId?: number
  chatId?: number
  path?: string
  children?: TreeNode[]
}

const treeRef = ref()
/** 数据变化后重建树，保证 default-expand-all 生效 */
const treeVersion = ref(0)

const treeData = computed<TreeNode[]>(() =>
  projectStore.projects.map((p) => ({
    key: `p-${p.id}`,
    type: 'project',
    label: p.name,
    projectId: p.id,
    path: p.path,
    children: chatStore.chatsByProject(p.id).map((c) => ({
      key: `c-${c.id}`,
      type: 'chat',
      label: c.title,
      projectId: p.id,
      chatId: c.id,
    })),
  })),
)

async function rebuildTree() {
  treeVersion.value += 1
  await nextTick()
}

async function addProject() {
  try {
    if (window.electronApi?.selectFolder) {
      const project = await projectStore.pickAndAdd()
      if (!project) return // 用户取消选择
      ElMessage.success(`已添加项目：${project.name}`)
    } else {
      // 浏览器环境降级：手动输入路径
      const { value } = await ElMessageBox.prompt('请输入本地 git 仓库的绝对路径', '添加项目', {
        confirmButtonText: '添加',
        cancelButtonText: '取消',
        inputPattern: /.+/,
        inputErrorMessage: '路径不能为空',
      })
      const project = await projectStore.add(value.trim())
      ElMessage.success(`已添加项目：${project.name}`)
    }
    await rebuildTree()
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg !== 'cancel' && msg !== 'close') ElMessage.error(msg)
  }
}

async function addChat(projectId: number) {
  try {
    const chat = await chatStore.createChat(projectId)
    await chatStore.selectChat(chat.id)
    await rebuildTree()
    ElMessage.success('已创建对话')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

async function removeChat(node: TreeNode) {
  if (!node.chatId) return
  try {
    await ElMessageBox.confirm(`删除对话「${node.label}」及其全部消息？`, '删除对话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await chatStore.removeChat(node.chatId)
    await rebuildTree()
    ElMessage.success('已删除对话')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

async function removeProject(node: TreeNode) {
  if (!node.projectId) return
  try {
    await ElMessageBox.confirm(
      `删除项目「${node.label}」及其全部对话？文件夹本身不会被删除。`,
      '删除项目',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await projectStore.remove(node.projectId)
    chatStore.chats = chatStore.chats.filter((c) => c.project_id !== node.projectId)
    if (chatStore.activeChat && chatStore.activeChat.project_id === node.projectId) {
      chatStore.clearActive()
    }
    await rebuildTree()
    ElMessage.success('已删除项目')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function onNodeClick(data: TreeNode) {
  if (data.type === 'chat' && data.chatId) {
    chatStore.selectChat(data.chatId).catch((e) =>
      ElMessage.error(e instanceof Error ? e.message : String(e)),
    )
  }
}

defineExpose({ rebuildTree })
</script>

<template>
  <div class="project-tree">
    <div class="tree-header">
      <span class="title">项目列表</span>
      <el-button size="small" type="primary" :icon="Plus" @click="addProject">添加项目</el-button>
    </div>

    <div class="tree-body" v-loading="projectStore.loading">
      <el-empty
        v-if="treeData.length === 0"
        description="还没有项目，点击「添加项目」选择 git 仓库文件夹"
        :image-size="72"
      />
      <el-tree
        v-else
        :key="treeVersion"
        ref="treeRef"
        :data="treeData"
        node-key="key"
        default-expand-all
        highlight-current
        :expand-on-click-node="false"
        @node-click="onNodeClick"
      >
        <template #default="{ data }">
          <div class="tree-node">
            <span class="node-label">
              <el-icon v-if="data.type === 'project'" class="node-icon"><FolderOpened /></el-icon>
              <el-icon v-else class="node-icon chat"><ChatLineRound /></el-icon>
              <span class="text" :title="data.path || data.label">{{ data.label }}</span>
            </span>
            <span class="node-actions" @click.stop>
              <el-button
                v-if="data.type === 'project'"
                text
                circle
                size="small"
                title="新建对话"
                :icon="Plus"
                @click="addChat(data.projectId)"
              />
              <el-button
                v-if="data.type === 'project'"
                text
                circle
                size="small"
                title="删除项目"
                :icon="Delete"
                @click="removeProject(data)"
              />
              <el-button
                v-if="data.type === 'chat'"
                text
                circle
                size="small"
                class="danger"
                title="删除对话"
                :icon="Delete"
                @click="removeChat(data)"
              />
            </span>
          </div>
        </template>
      </el-tree>
    </div>
  </div>
</template>

<style scoped>
.project-tree {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.tree-header .title {
  font-weight: 600;
  font-size: 14px;
}

.tree-body {
  flex: 1;
  overflow: auto;
  padding: 6px 4px;
}

.tree-node {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  padding-right: 2px;
}
.node-label {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.node-icon {
  color: var(--el-color-warning);
}
.node-icon.chat {
  color: var(--el-color-primary);
}
.node-label .text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.node-actions {
  display: none;
  flex: 0 0 auto;
  margin-left: auto;
}
.tree-node:hover .node-actions {
  display: inline-flex;
}
.node-actions .danger {
  color: var(--el-color-danger);
}
:deep(.el-tree-node__content) {
  height: 32px;
}
</style>
