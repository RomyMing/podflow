'use client'

import { useEffect } from 'react'

import { useTaskStore } from '@/stores/task-store'

const ACTIVE_STATUSES = new Set(['pending', 'processing'])
const POLL_INTERVAL_MS = 5000
const TASK_LIST_REFRESH_LIMIT = 100

export function TaskActivitySync() {
  const { tasks, currentTask, fetchTasks } = useTaskStore()

  const hasActiveTaskInList = tasks.some((task) => ACTIVE_STATUSES.has(task.status))
  const hasActiveCurrentTask = currentTask ? ACTIVE_STATUSES.has(currentTask.status) : false
  const shouldPoll = hasActiveTaskInList || hasActiveCurrentTask

  useEffect(() => {
    void fetchTasks(0, TASK_LIST_REFRESH_LIMIT, { silent: true })
  }, [fetchTasks])

  useEffect(() => {
    if (!shouldPoll) {
      return
    }

    const refresh = () => {
      void fetchTasks(0, TASK_LIST_REFRESH_LIMIT, { silent: true })
    }

    refresh()
    const intervalId = window.setInterval(refresh, POLL_INTERVAL_MS)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [fetchTasks, shouldPoll])

  return null
}
