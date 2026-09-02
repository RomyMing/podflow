'use client'

import { useCallback, useEffect, useRef } from 'react'

import { useTaskStore } from '@/stores/task-store'
import { TaskResponse } from '@/types/api'

const POLL_INTERVAL_MS = 5000

export function useTaskProgress(taskId: string | null) {
  const {
    currentTask,
    isLoading,
    error,
    fetchTaskById,
    subscribeToProgress,
    unsubscribeFromProgress,
  } = useTaskStore()

  const prevTaskIdRef = useRef<string | null>(null)
  const isCurrentTaskMatch = !!taskId && !!currentTask && currentTask.id === taskId
  const currentTaskStatus = isCurrentTaskMatch ? currentTask.status : null
  const isActiveTask = currentTaskStatus === 'pending' || currentTaskStatus === 'processing'

  useEffect(() => {
    if (!taskId || taskId === prevTaskIdRef.current) {
      return
    }

    prevTaskIdRef.current = taskId
    fetchTaskById(taskId)
  }, [taskId, fetchTaskById])

  useEffect(() => {
    if (!taskId || !isCurrentTaskMatch || !isActiveTask) {
      return
    }
    subscribeToProgress(taskId)

    return () => {
      unsubscribeFromProgress(taskId)
    }
  }, [isActiveTask, isCurrentTaskMatch, subscribeToProgress, taskId, unsubscribeFromProgress])

  useEffect(() => {
    if (!taskId || !isCurrentTaskMatch || !isActiveTask) {
      return
    }

    // Keep a low-frequency HTTP refresh even while websocket updates are
    // enabled. The connection registry only means a socket was created; it
    // does not prove that it is currently open. Polling is therefore the
    // safety net for blocked, disconnected, or exhausted websocket retries.
    const intervalId = window.setInterval(() => {
      fetchTaskById(taskId, { silent: true })
    }, POLL_INTERVAL_MS)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [fetchTaskById, isActiveTask, isCurrentTaskMatch, taskId])

  useEffect(() => {
    if (
      taskId &&
      isCurrentTaskMatch &&
      (currentTaskStatus === 'completed' || currentTaskStatus === 'failed')
    ) {
      fetchTaskById(taskId, { silent: true })
    }
  }, [currentTaskStatus, fetchTaskById, isCurrentTaskMatch, taskId])

  const retry = useCallback(() => {
    if (taskId) {
      fetchTaskById(taskId)
    }
  }, [taskId, fetchTaskById])

  return {
    task: currentTask as TaskResponse | null,
    isLoading,
    error,
    retry,
  }
}
