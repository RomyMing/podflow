'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { FileAudio } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { useTaskStore } from '@/stores/task-store'
import { TaskCard } from './task-card'

interface TaskListProps {
  maxItems?: number
}

export function TaskList({ maxItems = 5 }: TaskListProps) {
  const { tasks, isLoading, fetchTasks } = useTaskStore()

  useEffect(() => {
    fetchTasks(0, maxItems)
  }, [fetchTasks, maxItems])

  if (isLoading && tasks.length === 0) {
    return (
      <div className="task-list">
        <div className="task-list__header">
          <h3 className="task-list__title">最近任务</h3>
        </div>
        <div className="task-list__items">
          {[1, 2, 3].map((item) => (
            <div key={item} className="task-list__skeleton">
              <Skeleton className="w-10 h-10 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!isLoading && tasks.length === 0) {
    return (
      <div className="task-list">
        <div className="task-list__header">
          <h3 className="task-list__title">最近任务</h3>
        </div>
        <div className="task-list__empty">
          <FileAudio className="task-list__empty-icon" />
          <p className="task-list__empty-text">还没有任务记录</p>
          <p className="task-list__empty-hint">上传一段本地音频，创建你的第一个翻译任务。</p>
        </div>
      </div>
    )
  }

  const displayTasks = tasks.slice(0, maxItems)

  return (
    <div className="task-list" id="recent-tasks">
      <div className="task-list__header">
        <h3 className="task-list__title">最近任务</h3>
        {tasks.length > maxItems && (
          <Link href="/tasks" className="task-list__view-all">
            查看全部
          </Link>
        )}
      </div>
      <div className="task-list__items">
        {displayTasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>
    </div>
  )
}
