'use client'

import React from 'react'
import { Loader2, X } from 'lucide-react'
import { TaskService } from '@/services/task-service'
import { TaskSegmentResponse } from '@/types/api'
import './transcript-drawer.css'

interface TranscriptDrawerProps {
  taskId: string
  open: boolean
  onClose: () => void
}

function formatTime(seconds: number): string {
  if (!seconds || isNaN(seconds)) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export function TranscriptDrawer({ taskId, open, onClose }: TranscriptDrawerProps) {
  const [segments, setSegments] = React.useState<TaskSegmentResponse[] | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const loadedRef = React.useRef(false)

  React.useEffect(() => {
    if (!open || loadedRef.current || !taskId) {
      return
    }
    loadedRef.current = true
    let cancelled = false
    setLoading(true)
    setError(null)
    TaskService.getSegments(taskId)
      .then((data) => {
        if (!cancelled) setSegments(data)
      })
      .catch(() => {
        if (!cancelled) {
          setError('加载转写内容失败，请稍后重试。')
          loadedRef.current = false
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, taskId])

  return (
    <aside
      className={`transcript-drawer ${open ? 'transcript-drawer--open' : ''}`}
      aria-hidden={!open}
      id="transcript-drawer"
    >
      <header className="transcript-drawer__header">
        <div>
          <h2 className="transcript-drawer__title">双语对照</h2>
          <p className="transcript-drawer__subtitle">原文 / 译文 · 按时间轴与说话人排列</p>
        </div>
        <button
          type="button"
          className="transcript-drawer__close"
          onClick={onClose}
          aria-label="关闭双语对照"
          id="transcript-drawer-close"
        >
          <X size={18} />
        </button>
      </header>

      <div className="transcript-drawer__body">
        {loading && (
          <div className="transcript-drawer__state">
            <Loader2 size={18} className="animate-spin" />
            正在加载转写内容…
          </div>
        )}

        {!loading && error && <p className="transcript-drawer__state">{error}</p>}

        {!loading && !error && segments && segments.length === 0 && (
          <p className="transcript-drawer__state">
            暂无转写内容。任务完成转写与翻译后，这里会显示逐段双语对照。
          </p>
        )}

        {!loading && !error && segments && segments.length > 0 && (
          <div className="transcript-drawer__list">
            {segments.map((seg) => (
              <article className="transcript-drawer__seg" key={seg.index}>
                <div className="transcript-drawer__seg-meta">
                  <span className="transcript-drawer__seg-speaker">{seg.speaker_label ?? '未知说话人'}</span>
                  <span>
                    {formatTime(seg.start_time)} – {formatTime(seg.end_time)}
                  </span>
                </div>
                {seg.original_text && <p className="transcript-drawer__seg-original">{seg.original_text}</p>}
                {seg.translated_text && <p className="transcript-drawer__seg-translated">{seg.translated_text}</p>}
              </article>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
