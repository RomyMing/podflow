import { TaskResponse } from '@/types/api'

export function getTaskTitle(task: Pick<TaskResponse, 'id' | 'source_file_name'>): string {
  const trimmedName = task.source_file_name?.trim()
  if (trimmedName) {
    return trimmedName
  }

  return `任务 #${task.id.slice(0, 8)}`
}
