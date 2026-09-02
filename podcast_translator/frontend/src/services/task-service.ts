import { AxiosProgressEvent } from 'axios'

import { getAccessToken } from '@/lib/auth'
import { TaskConfig, TaskResponse, TaskSegmentResponse } from '@/types/api'

import { apiClient, uploadApiClient } from './api-client'

export const TaskService = {
  async createTask(
    file: File,
    config?: TaskConfig,
    onUploadProgress?: (progressEvent: AxiosProgressEvent) => void
  ): Promise<TaskResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (config) {
      formData.append('config', JSON.stringify(config))
    }

    const token = getAccessToken()
    const headers: Record<string, string> = {
      'Content-Type': 'multipart/form-data',
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    // In local `next dev`, large uploads bypass the Next rewrite proxy and hit
    // the backend directly to avoid proxy body-size limits and buffering.
    const { data } = await uploadApiClient.post<TaskResponse>('/tasks', formData, {
      headers,
      onUploadProgress,
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
    })

    return data
  },

  async listTasks(skip: number = 0, limit: number = 20): Promise<TaskResponse[]> {
    const { data } = await apiClient.get<TaskResponse[]>('/tasks', {
      params: { skip, limit },
    })
    return data
  },

  async getTask(id: string): Promise<TaskResponse> {
    const { data } = await apiClient.get<TaskResponse>(`/tasks/${id}`)
    return data
  },

  async getSegments(id: string, skip: number = 0, limit: number = 500): Promise<TaskSegmentResponse[]> {
    const { data } = await apiClient.get<TaskSegmentResponse[]>(`/tasks/${id}/segments`, {
      params: { skip, limit },
    })
    return data
  },

  async pauseTask(id: string): Promise<TaskResponse> {
    const { data } = await apiClient.post<TaskResponse>(`/tasks/${id}/pause`)
    return data
  },

  async deleteTask(id: string): Promise<void> {
    await apiClient.delete(`/tasks/${id}`)
  },

  async resumeTask(
    id: string,
    config?: Pick<TaskConfig, 'translation_provider' | 'voice_clone_provider' | 'voice_clone_mode' | 'voice_clone_consent_confirmed'>,
  ): Promise<TaskResponse> {
    const payload = config ? { config } : undefined
    const { data } = await apiClient.post<TaskResponse>(`/tasks/${id}/resume`, payload)
    return data
  },
}
