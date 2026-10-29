import { defineStore } from 'pinia'
import * as api from '@/api'
import type { Project } from '@/types/api'

interface ProjectState {
  projects: Project[]
  loading: boolean
}

export const useProjectStore = defineStore('project', {
  state: (): ProjectState => ({
    projects: [],
    loading: false,
  }),
  actions: {
    async fetch() {
      this.loading = true
      try {
        this.projects = await api.listProjects()
      } finally {
        this.loading = false
      }
    },
    /** 打开原生目录选择框并添加项目；取消返回 null */
    async pickAndAdd(): Promise<Project | null> {
      let path: string | null = null
      if (window.electronApi?.selectFolder) {
        path = await window.electronApi.selectFolder()
      }
      if (!path) return null
      return this.add(path)
    },
    async add(path: string): Promise<Project> {
      const project = await api.createProject(path)
      this.projects.unshift(project)
      return project
    },
    async remove(id: number) {
      await api.deleteProject(id)
      this.projects = this.projects.filter((p) => p.id !== id)
    },
  },
})
