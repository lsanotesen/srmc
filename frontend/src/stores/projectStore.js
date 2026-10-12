/**
 * 项目树全局缓存 Store
 *
 * 设计原则：
 * 1. 静态数据一次性加载 - 页面初始化时调用 fetchTree()，5分钟内不再请求
 * 2. 扁平化索引 - 提供 O(1) 查找：subsystemsByProject / groupsBySubsystem
 * 3. 数据变更后强制刷新 - 调用 invalidate() 重新加载
 *
 * 使用方式：
 *   import { useProjectStore } from '@/stores/projectStore'
 *   const projectStore = useProjectStore()
 *   await projectStore.fetchTree()                          // 初始化加载
 *   const subs = projectStore.subsystemsByProject(projId)   // 从缓存取
 *   projectStore.invalidate()                               // 数据变更后刷新
 */
import { defineStore } from 'pinia'
import axios from '@/utils/axios'

// 缓存 TTL（5 分钟），与后端 Redis TTL 一致
const TREE_TTL = 5 * 60 * 1000

export const useProjectStore = defineStore('project', {
  state: () => ({
    // 原始树结构：[{id, name, subsystems: [{id, subsystem_name, service_groups: [...]}]}]
    tree: [],
    lastFetchTime: 0,
    loading: false,
    error: null,

    // 扁平化索引，O(1) 查找
    // subsystemIndex: Map<project_id, Subsystem[]>
    // groupIndex: Map<subsystem_id, ServiceGroup[]>
    subsystemIndex: new Map(),
    groupIndex: new Map()
  }),

  getters: {
    /**
     * 按 project_id 获取子系统列表（从缓存，无请求）
     * @param {number} projectId
     * @returns {Array} 子系统列表 [{id, subsystem_name, ...}]
     */
    subsystemsByProject: (state) => (projectId) => {
      if (!projectId) return []
      return state.subsystemIndex.get(Number(projectId)) || []
    },

    /**
     * 按 subsystem_id 获取分组列表（从缓存，无请求）
     * @param {number} subsystemId
     * @returns {Array} 分组列表 [{id, group_name, ...}]
     */
    groupsBySubsystem: (state) => (subsystemId) => {
      if (!subsystemId) return []
      return state.groupIndex.get(Number(subsystemId)) || []
    },

    /**
     * 是否已加载过树数据
     */
    isLoaded: (state) => state.tree.length > 0,

    /**
     * 缓存是否过期
     */
    isExpired: (state) => Date.now() - state.lastFetchTime > TREE_TTL
  },

  actions: {
    /**
     * 加载项目树（带缓存）
     * @param {boolean} force - 强制刷新，忽略缓存
     * @returns {Promise<Array>} 树数据
     */
    async fetchTree(force = false) {
      // 缓存有效且非强制刷新，直接返回
      if (!force && !this.isExpired && this.isLoaded) {
        return this.tree
      }
      // 防止并发请求
      if (this.loading) {
        return this.tree
      }

      this.loading = true
      this.error = null
      try {
        const response = await axios.get('/api/projects/tree')
        if (response.data.code === 0) {
          this.tree = response.data.data || []
          this.lastFetchTime = Date.now()
          this.buildIndex()
        } else {
          this.error = response.data.message || '加载项目树失败'
        }
      } catch (err) {
        this.error = err.message || '网络错误'
        console.error('[projectStore] 加载项目树失败:', err)
      } finally {
        this.loading = false
      }
      return this.tree
    },

    /**
     * 构建扁平化索引，供 O(1) 查找
     * 在 tree 数据变更后调用
     */
    buildIndex() {
      this.subsystemIndex = new Map()
      this.groupIndex = new Map()

      for (const project of this.tree) {
        const subsystems = project.subsystems || []
        this.subsystemIndex.set(project.id, subsystems)
        for (const sub of subsystems) {
          this.groupIndex.set(sub.id, sub.service_groups || [])
        }
      }
    },

    /**
     * 清空缓存（退出登录/切换账号时调用）
     * 避免切换账号后残留上一个账号的项目树数据
     */
    reset() {
      this.tree = []
      this.lastFetchTime = 0
      this.loading = false
      this.error = null
      this.subsystemIndex = new Map()
      this.groupIndex = new Map()
    },

    /**
     * 数据变更后强制刷新缓存
     * 在新增/编辑/删除 项目/子系统/分组 后调用
     */
    async invalidate() {
      this.lastFetchTime = 0
      return this.fetchTree(true)
    }
  }
})
