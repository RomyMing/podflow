'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AlertCircle, CheckCircle2, Clock, Download, Headphones, Loader2, PauseCircle, Play } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { getTaskTitle } from '@/lib/task-title'
import { TaskResponse } from '@/types/api'

interface TaskCardProps {
  task: TaskResponse
  variant?: 'compact' | 'detailed'
}

const STATUS_CONFIG = {
  completed: {
    label: '已完成',
    variant: 'success' as const,
    icon: CheckCircle2,
  },
  processing: {
    label: '处理中',
    variant: 'warning' as const,
    icon: Loader2,
  },
  paused: {
    label: '已暂停',
    variant: 'warning' as const,
    icon: PauseCircle,
  },
  failed: {
    label: '失败',
    variant: 'error' as const,
    icon: AlertCircle,
  },
  pending: {
    label: '排队中',
    variant: 'default' as const,
    icon: Clock,
  },
}

function formatDuration(seconds: number | null): string {
  if (!seconds) {
    return ''
  }

  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)

  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatTimeAgo(dateStr: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) {
    return '刚刚'
  }
  if (diffMins < 60) {
    return `${diffMins} 分钟前`
  }

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) {
    return `${diffHours} 小时前`
  }

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) {
    return `${diffDays} 天前`
  }

  return date.toLocaleDateString('zh-CN')
}

function TaskCardDetailed({ task }: { task: TaskResponse }) {
  const router = useRouter()
  const statusInfo = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending
  const StatusIcon = statusInfo.icon

  return (
    <div className="task-card task-card--detailed" id={`task-card-${task.id}`}>
      <div className="task-card__icon-wrapper">
        <Headphones className="task-card__icon" />
      </div>

      <div className="task-card__content">
        <p className="task-card__title">{getTaskTitle(task)}</p>
        <p className="task-card__meta">
          {task.audio_duration ? `${formatDuration(task.audio_duration)} · ` : ''}
          {formatTimeAgo(task.created_at)}
        </p>
      </div>

      <div className="task-card__status">
        {task.status === 'processing' && (
          <span className="task-card__progress-text">{task.progress_percent}%</span>
        )}
        <Badge variant={statusInfo.variant} className="task-card__status-badge">
          <StatusIcon className={`w-3 h-3 ${task.status === 'processing' ? 'animate-spin' : ''}`} />
          {statusInfo.label}
        </Badge>
      </div>

      <div className="task-card__actions">
        <button
          className="task-card__action-btn task-card__action-btn--ghost"
          onClick={() => router.push(`/tasks/${task.id}`)}
          aria-label="查看详情"
          id={`task-detail-${task.id}`}
        >
          详情
        </button>

        {task.status === 'completed' && task.output_audio_url && (
          <>
            <a
              className="task-card__action-btn task-card__action-btn--primary"
              href={`/tasks/${task.id}`}
              aria-label="播放结果"
              id={`task-play-${task.id}`}
            >
              <Play className="w-3 h-3" />
              播放
            </a>
            <a
              className="task-card__action-btn task-card__action-btn--ghost"
              href={task.output_audio_url}
              download
              aria-label="下载音频"
              id={`task-download-${task.id}`}
            >
              <Download className="w-3 h-3" />
              下载
            </a>
          </>
        )}
      </div>
    </div>
  )
}

export function TaskCard({ task, variant = 'compact' }: TaskCardProps) {
  if (variant === 'detailed') {
    return <TaskCardDetailed task={task} />
  }

  const statusInfo = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending
  const StatusIcon = statusInfo.icon

  return (
    <Link href={`/tasks/${task.id}`} className="task-card" id={`task-card-${task.id}`}>
      <div className="task-card__icon-wrapper">
        <Headphones className="task-card__icon" />
      </div>

      <div className="task-card__content">
        <p className="task-card__title">{getTaskTitle(task)}</p>
        <p className="task-card__meta">
          {task.audio_duration ? `${formatDuration(task.audio_duration)} · ` : ''}
          {formatTimeAgo(task.created_at)}
        </p>
      </div>

      <div className="task-card__status">
        {task.status === 'processing' && (
          <span className="task-card__progress-text">{task.progress_percent}%</span>
        )}
        <Badge variant={statusInfo.variant} className="task-card__status-badge">
          <StatusIcon className={`w-3 h-3 ${task.status === 'processing' ? 'animate-spin' : ''}`} />
          {statusInfo.label}
        </Badge>
      </div>
    </Link>
  )
}
