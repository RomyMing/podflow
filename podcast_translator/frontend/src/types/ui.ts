/**
 * UI 状态类型定义 — 前端独有类型
 */

// ============================================================
// Toast Notification (PROJECT_UI.md §9.2)
// ============================================================

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number      // ms, 0 = 不自动消失
  dismissible?: boolean  // 是否显示关闭按钮
}

// ============================================================
// Navigation
// ============================================================

export interface NavItem {
  label: string
  href: string
  icon: string       // Lucide icon name
  active?: boolean
}

// ============================================================
// Task UI States
// ============================================================

export type TaskFilterStatus = 'all' | 'processing' | 'paused' | 'completed' | 'failed'

export type TaskSortBy = 'newest' | 'oldest' | 'duration'

export interface TaskFilterState {
  status: TaskFilterStatus
  sortBy: TaskSortBy
  page: number
  pageSize: number
}

// ============================================================
// Pipeline Step (for progress UI)
// ============================================================

export interface PipelineStep {
  key: string
  label: string
  icon: string
  status: 'pending' | 'active' | 'paused' | 'completed' | 'failed'
  progress?: number     // 0-100
}

// ============================================================
// Upload State
// ============================================================

export type UploadStatus = 'idle' | 'selecting' | 'uploading' | 'processing' | 'error'

export interface UploadState {
  status: UploadStatus
  file: File | null
  url: string
  progress: number      // 0-100
  error: string | null
}

// ============================================================
// Task Config Panel (原型图扩展)
// ============================================================

export interface TaskConfigFormData {
  targetLanguage: string
  speakerCount: number
  outputFormat: 'mp3' | 'wav' | 'aac'
}

// ============================================================
// Auth UI State
// ============================================================

export type AuthStep = 'phone' | 'code' | 'submitting'
