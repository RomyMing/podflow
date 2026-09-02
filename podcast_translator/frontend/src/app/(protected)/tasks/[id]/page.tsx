'use client'

import React from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, CheckCircle, Clock, Headphones, Loader2, PauseCircle, RotateCcw, Trash2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TaskCompleteCard } from '@/components/task/task-complete-card'
import { TranscriptDrawer } from '@/components/task/transcript-drawer'
import { TaskErrorCard } from '@/components/task/task-error-card'
import { PipelineProgress } from '@/components/task/pipeline-progress'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import {
  getTranslationProviderPreference,
  getVoiceCloneConsentPreference,
  getVoiceCloneModePreference,
} from '@/lib/preferences'
import { formatTaskErrorMessage, formatTaskLanguage, formatTaskTechnicalCode } from '@/lib/task-display'
import { getTaskTitle } from '@/lib/task-title'
import { TaskService } from '@/services/task-service'
import './task-detail.css'

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

const STATUS_BADGE_CONFIG: Record<string, {
  label: string
  icon: React.ComponentType<{ className?: string }>
  className: string
}> = {
  completed: {
    label: '已完成',
    icon: CheckCircle,
    className: 'task-header__status-badge--completed',
  },
  failed: {
    label: '失败',
    icon: XCircle,
    className: 'task-header__status-badge--failed',
  },
  paused: {
    label: '已暂停',
    icon: PauseCircle,
    className: 'task-header__status-badge--paused',
  },
  processing: {
    label: '处理中',
    icon: Loader2,
    className: 'task-header__status-badge--processing',
  },
  pending: {
    label: '排队中',
    icon: Clock,
    className: 'task-header__status-badge--pending',
  },
}

const ACTIVE_STATUS_NOTICE: Record<'pending' | 'processing', { title: string; description: string }> = {
  pending: {
    title: '文件已接收，正在等待处理资源',
    description: '当前音频已经入队，任务会在后台处理器可用后自动开始。只有状态变为“已完成”才代表整条处理链路最终成功。',
  },
  processing: {
    title: '文件已接收，后台正在处理中',
    description: '上传成功仅表示文件已进入处理流程。请以此页面的最终状态为准，只有状态变为“已完成”才代表任务真正成功。',
  },
}

const STAGE_RUN_LABELS: Record<string, string> = {
  uploaded: '已上传',
  preparing: '准备任务',
  source_separation: '音轨分离',
  speaker_diarization: '说话人识别',
  asr_transcription: '语音转写',
  translation: '文本翻译',
  voice_clone_tts: '语音合成',
  temporal_alignment: '时间对齐',
  final_mixing: '最终混音',
}

const STAGE_RUN_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  processing: '进行中',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  paused: '已暂停',
  skipped: '已跳过',
}

const SPEAKER_GENDER_LABELS: Record<string, string> = {
  male: '男声',
  female: '女声',
  unknown: '性别未知',
}

const SPEAKER_ENROLLMENT_STATUS_LABELS: Record<string, string> = {
  enrolled: '已完成声音克隆',
  fallback: '使用预设音色',
  fallback_failed: '克隆失败，使用预设音色',
  fallback_unreachable_ref: '参考音频不可访问，使用预设音色',
  fallback_no_ref: '缺少参考音频，使用预设音色',
  disabled: '未启用声音克隆',
  pending: '等待克隆',
}

const SPEAKER_PROVIDER_LABELS: Record<string, string> = {
  elevenlabs: 'ElevenLabs',
  cosyvoice: 'CosyVoice',
  mock: 'Mock',
}

const SPEAKER_FALLBACK_REASON_LABELS: Record<string, string> = {
  elevenlabs_clone_failed: 'ElevenLabs 克隆失败',
  cosyvoice_enrollment_failed: 'CosyVoice 克隆失败',
  reference_audio_unreachable: '参考音频不可访问',
  missing_reference_audio: '缺少参考音频',
  voice_clone_disabled: '已关闭声纹克隆',
  preset_fallback: '使用预设音色',
}

function formatStageRunDuration(seconds: number): string {
  if (seconds <= 0) {
    return '少于 1 秒'
  }

  if (seconds < 60) {
    return `${seconds} 秒`
  }

  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes} 分 ${remainingSeconds} 秒` : `${minutes} 分`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  const parts = [`${hours} 小时`]
  if (remainingMinutes > 0) {
    parts.push(`${remainingMinutes} 分`)
  }
  if (remainingSeconds > 0) {
    parts.push(`${remainingSeconds} 秒`)
  }
  return parts.join(' ')
}

function formatStageRunItems(itemsDone: number | null, itemsTotal: number | null): string {
  if (!itemsTotal) {
    return '无分项'
  }

  return `已处理 ${itemsDone ?? 0}/${itemsTotal}`
}

function formatSpeakerLabel(label: string): string {
  const match = label.match(/^SPEAKER_(\d+)$/)
  if (match) {
    return `说话人 ${Number(match[1]) + 1}`
  }
  return label || '未知说话人'
}

function formatSpeakerGender(gender: string | null): string {
  if (!gender) {
    return '性别未知'
  }
  return SPEAKER_GENDER_LABELS[gender] || '性别未知'
}

function formatSpeakerEnrollmentStatus(status: string | null): string {
  if (!status) {
    return '未记录克隆状态'
  }
  return SPEAKER_ENROLLMENT_STATUS_LABELS[status] || '未知克隆状态'
}

function formatSpeakerVoiceInfo(
  voiceId: string | null,
  voiceModel: string | null,
  voiceProvider: string | null,
  fallbackReason: string | null,
): string {
  const provider = voiceProvider ? SPEAKER_PROVIDER_LABELS[voiceProvider] || voiceProvider : null
  if (voiceId) {
    return provider ? `${provider} 克隆音色` : '克隆音色已就绪'
  }
  if (voiceModel) {
    return provider ? `${provider} 预设音色` : '预设音色已就绪'
  }
  if (fallbackReason) {
    return SPEAKER_FALLBACK_REASON_LABELS[fallbackReason] || fallbackReason
  }
  return '预设音色'
}

export default function TaskDetailPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = params?.id as string | undefined
  const { task, isLoading, error, retry } = useTaskProgress(taskId || null)
  const [isResuming, setIsResuming] = React.useState(false)
  const [resumeError, setResumeError] = React.useState<string | null>(null)
  const [isPausing, setIsPausing] = React.useState(false)
  const [pauseRequested, setPauseRequested] = React.useState(false)
  const [actionError, setActionError] = React.useState<string | null>(null)
  const [isDeleting, setIsDeleting] = React.useState(false)
  const [transcriptOpen, setTranscriptOpen] = React.useState(false)

  async function handlePause() {
    if (!taskId) {
      return
    }
    setIsPausing(true)
    setActionError(null)
    try {
      await TaskService.pauseTask(taskId)
      setPauseRequested(true)
      retry()
    } catch (err) {
      setActionError(formatTaskErrorMessage(err instanceof Error ? err.message : null) || '暂停任务失败')
    } finally {
      setIsPausing(false)
    }
  }

  async function handleDelete() {
    if (!taskId) {
      return
    }
    if (!window.confirm('确定删除该任务吗？此操作会一并删除生成的音频与字幕，且不可恢复。')) {
      return
    }
    setIsDeleting(true)
    setActionError(null)
    try {
      await TaskService.deleteTask(taskId)
      router.push('/')
    } catch (err) {
      setActionError(formatTaskErrorMessage(err instanceof Error ? err.message : null) || '删除任务失败')
      setIsDeleting(false)
    }
  }

  async function handleResume() {
    if (!taskId) {
      return
    }
    setIsResuming(true)
    setResumeError(null)
    try {
      await TaskService.resumeTask(taskId, {
        translation_provider: getTranslationProviderPreference(),
        voice_clone_provider: 'elevenlabs',
        voice_clone_mode: getVoiceCloneModePreference(),
        voice_clone_consent_confirmed: getVoiceCloneConsentPreference(),
      })
      retry()
    } catch (err) {
      setResumeError(formatTaskErrorMessage(err instanceof Error ? err.message : null) || '继续生成失败')
    } finally {
      setIsResuming(false)
    }
  }

  if (isLoading && !task) {
    return (
      <div className="task-detail-page">
        <button className="task-detail__back" onClick={() => router.back()}>
          <ArrowLeft className="task-detail__back-icon" />
          返回
        </button>

        <div className="task-detail__skeleton">
          <Skeleton className="task-detail__skeleton-icon" />
          <Skeleton className="task-detail__skeleton-title" />
          <Skeleton className="task-detail__skeleton-subtitle" />
          <Skeleton className="task-detail__skeleton-panel" />
        </div>
      </div>
    )
  }

  if (error && !task) {
    return (
      <div className="task-detail-page">
        <button className="task-detail__back" onClick={() => router.back()}>
          <ArrowLeft className="task-detail__back-icon" />
          返回
        </button>

        <div className="task-detail__error">
          <Headphones className="task-detail__error-icon" />
          <p className="task-detail__error-text">{formatTaskErrorMessage(error) || '任务详情加载失败'}</p>
          <Button variant="primary" size="md" onClick={retry} className="task-detail__action-btn">
            重新加载
          </Button>
        </div>
      </div>
    )
  }

  if (!task) {
    return null
  }

  const statusBadge = STATUS_BADGE_CONFIG[task.status] || STATUS_BADGE_CONFIG.pending
  const StatusBadgeIcon = statusBadge.icon
  const activeStatusNotice =
    task.status === 'pending' || task.status === 'processing'
      ? ACTIVE_STATUS_NOTICE[task.status]
      : null
  const durationText = task.audio_duration ? formatDuration(task.audio_duration) : null
  const timeAgoText = formatTimeAgo(task.created_at)
  const metaParts = [
    durationText ? `时长 ${durationText}` : null,
    `上传于 ${timeAgoText}`,
  ].filter(Boolean).join(' · ')

  return (
    <div className="task-detail-page">
      <button
        className="task-detail__back"
        onClick={() => router.back()}
        id="task-detail-back"
      >
        <ArrowLeft className="task-detail__back-icon" />
        返回
      </button>

      <div className="task-header" id="task-header">
        <div className="task-header__icon-wrapper">
          <Headphones className="task-header__icon" />
        </div>

        <div className="task-header__title-row">
          <h1 className="task-header__title">{getTaskTitle(task)}</h1>
          <span className={`task-header__status-badge ${statusBadge.className}`}>
            <StatusBadgeIcon className={`w-3.5 h-3.5 ${task.status === 'processing' ? 'animate-spin' : ''}`} />
            {statusBadge.label}
          </span>
        </div>

        {task.config?.target_language && (
          <p className="task-header__subtitle">
            目标语言 {formatTaskLanguage(task.config.target_language)}
            {task.config.speaker_count ? ` · ${task.config.speaker_count} 位说话人` : ''}
          </p>
        )}

        <p className="task-header__meta">{metaParts}</p>
      </div>

      {activeStatusNotice && (
        <div className="task-detail__status-note" id="task-status-note">
          <p className="task-detail__status-note-title">{activeStatusNotice.title}</p>
          <p className="task-detail__status-note-description">{activeStatusNotice.description}</p>
        </div>
      )}

      {(task.status === 'processing' || task.status === 'pending' || task.status === 'paused') && (
        <PipelineProgress
          currentStage={task.current_stage}
          progressPercent={task.progress_percent}
          stageProgressPercent={task.stage_progress_percent}
          etaSeconds={task.eta_seconds}
          taskStatus={task.status}
        />
      )}

      {(task.status === 'processing' || task.status === 'pending') && (
        <div className="task-detail__action-row" id="task-pause-section">
          <Button
            variant="secondary"
            size="md"
            onClick={handlePause}
            disabled={isPausing || pauseRequested}
            className="task-detail__action-btn"
          >
            <PauseCircle className="w-4 h-4" />
            {isPausing ? '暂停中...' : pauseRequested ? '已请求暂停' : '暂停任务'}
          </Button>
          {pauseRequested && (
            <p className="task-detail__hint">已请求暂停，将在当前阶段完成后停下，可继续或删除。</p>
          )}
          {actionError && <p className="task-detail__paused-error">{actionError}</p>}
        </div>
      )}

      {task.status === 'completed' && task.output_audio_url && (
        <TaskCompleteCard
          audioUrl={task.output_audio_url}
          taskId={task.id}
          onViewTranscript={() => setTranscriptOpen(true)}
        />
      )}

      <TranscriptDrawer taskId={task.id} open={transcriptOpen} onClose={() => setTranscriptOpen(false)} />

      {task.status === 'paused' && (
        <div className="task-detail__paused-card" id="task-paused-card">
          <p className="task-detail__paused-title">
            {task.pause_reason_code === 'user_paused' ? '任务已暂停' : '生成已暂停'}
          </p>
          <p className="task-detail__paused-desc">
            {task.pause_reason_code === 'user_paused'
              ? '任务已手动暂停，可从当前阶段继续生成，或删除该任务。'
              : formatTaskErrorMessage(task.error_message) ||
                '外部服务额度、余额或接口密钥需要处理。处理完成后可以从当前阶段继续生成。'}
          </p>
          {task.pause_reason_code !== 'user_paused' && (task.pause_reason_code || task.provider_error_code) && (
            <p className="task-detail__paused-code">
              {formatTaskTechnicalCode(task.pause_reason_code) || '外部服务已暂停'}
              {task.provider_error_code ? ` · ${formatTaskTechnicalCode(task.provider_error_code) || '未识别错误代码'}` : ''}
            </p>
          )}
          {(resumeError || actionError) && (
            <p className="task-detail__paused-error">{resumeError || actionError}</p>
          )}
          <div className="task-detail__action-row">
            <Button
              variant="primary"
              size="md"
              onClick={handleResume}
              disabled={isResuming || isDeleting}
              className="task-detail__action-btn task-detail__resume-btn"
            >
              <RotateCcw className="w-4 h-4" />
              {isResuming ? '正在入队...' : '继续生成'}
            </Button>
            <Button
              variant="danger"
              size="md"
              onClick={handleDelete}
              disabled={isDeleting || isResuming}
              className="task-detail__action-btn"
            >
              <Trash2 className="w-4 h-4" />
              {isDeleting ? '删除中...' : '删除任务'}
            </Button>
          </div>
        </div>
      )}

      {!!task.stage_runs?.length && (
        <div className="task-detail__stage-runs">
          <p className="task-detail__section-title">阶段耗时</p>
          <div className="task-detail__stage-run-list">
            {task.stage_runs.map((run) => {
              const started = new Date(run.started_at).getTime()
              const finished = run.finished_at ? new Date(run.finished_at).getTime() : Date.now()
              const seconds = Math.max(0, Math.round((finished - started) / 1000))
              return (
                <div className="task-detail__stage-run" key={`${run.stage}-${run.attempt}`}>
                  <span title={STAGE_RUN_LABELS[run.stage] || '未识别阶段'}>{STAGE_RUN_LABELS[run.stage] || '未识别阶段'}</span>
                  <span title={STAGE_RUN_STATUS_LABELS[run.status] || '未知状态'}>{STAGE_RUN_STATUS_LABELS[run.status] || '未知状态'}</span>
                  <span>{formatStageRunDuration(seconds)}</span>
                  <span>{formatStageRunItems(run.items_done, run.items_total)}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {!!task.speakers?.length && (
        <div className="task-detail__speakers">
          <p className="task-detail__section-title">声音状态</p>
          {task.speakers.map((speaker) => (
            <div className="task-detail__speaker" key={speaker.label}>
              <span title={formatSpeakerLabel(speaker.label)}>{formatSpeakerLabel(speaker.label)}</span>
              <span title={formatSpeakerGender(speaker.gender)}>{formatSpeakerGender(speaker.gender)}</span>
              <span title={formatSpeakerEnrollmentStatus(speaker.enrollment_status)}>
                {formatSpeakerEnrollmentStatus(speaker.enrollment_status)}
              </span>
              <span title={formatSpeakerVoiceInfo(speaker.voice_id, speaker.voice_model, speaker.voice_provider, speaker.fallback_reason)}>
                {formatSpeakerVoiceInfo(speaker.voice_id, speaker.voice_model, speaker.voice_provider, speaker.fallback_reason)}
              </span>
            </div>
          ))}
        </div>
      )}

      {task.status === 'failed' && (
        <TaskErrorCard
          errorMessage={task.error_message}
          currentStage={task.current_stage}
        />
      )}
    </div>
  )
}
