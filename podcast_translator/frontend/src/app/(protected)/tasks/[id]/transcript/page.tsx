'use client'

import React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { TaskService } from '@/services/task-service'
import { TaskSegmentResponse } from '@/types/api'

function formatTime(seconds: number): string {
  if (!seconds || isNaN(seconds)) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function TranscriptPage() {
  const params = useParams<{ id: string }>()
  const id = params?.id as string

  const [segments, setSegments] = React.useState<TaskSegmentResponse[] | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    setError(null)
    TaskService.getSegments(id)
      .then((data) => {
        if (!cancelled) setSegments(data)
      })
      .catch(() => {
        if (!cancelled) setError('加载转写内容失败，请稍后重试。')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  return (
    <main style={{ maxWidth: 760, margin: '0 auto', padding: '32px 24px 64px' }}>
      <Link
        href={`/tasks/${id}`}
        id="transcript-back-btn"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 14,
          color: 'var(--color-text-secondary)',
          textDecoration: 'none',
          marginBottom: 20,
        }}
      >
        <ArrowLeft size={16} />
        返回任务详情
      </Link>

      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6, color: 'var(--color-text-primary)' }}>
        双语对照稿
      </h1>
      <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 24 }}>
        逐段对照原文与译文，按说话人和时间轴排列。
      </p>

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--color-text-secondary)', padding: '40px 0' }}>
          <Loader2 size={18} className="animate-spin" />
          正在加载转写内容…
        </div>
      )}

      {!loading && error && (
        <p style={{ color: 'var(--color-text-secondary)', padding: '40px 0' }}>{error}</p>
      )}

      {!loading && !error && segments && segments.length === 0 && (
        <p style={{ color: 'var(--color-text-secondary)', padding: '40px 0', lineHeight: 1.7 }}>
          暂无转写内容。任务完成转写与翻译后，这里会显示逐段双语对照。
        </p>
      )}

      {!loading && !error && segments && segments.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {segments.map((seg) => (
            <article
              key={seg.index}
              style={{
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md, 10px)',
                padding: '14px 16px',
                background: 'var(--color-bg-secondary)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  fontSize: 12,
                  color: 'var(--color-text-secondary)',
                  marginBottom: 8,
                }}
              >
                <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  {seg.speaker_label ?? '未知说话人'}
                </span>
                <span>
                  {formatTime(seg.start_time)} – {formatTime(seg.end_time)}
                </span>
              </div>
              {seg.original_text && (
                <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.7, margin: '0 0 6px' }}>
                  {seg.original_text}
                </p>
              )}
              {seg.translated_text && (
                <p style={{ fontSize: 15, color: 'var(--color-accent)', fontWeight: 500, lineHeight: 1.7, margin: 0 }}>
                  {seg.translated_text}
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </main>
  )
}
