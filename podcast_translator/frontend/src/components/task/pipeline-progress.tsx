'use client'

import React from 'react'
import { Check, Circle, Loader2, PauseCircle, XCircle } from 'lucide-react'
import { PipelineStage } from '@/types/api'

const PIPELINE_STEPS: {
  id: string
  label: string
  stages: PipelineStage[]
}[] = [
  {
    id: 'source_separation',
    label: '音源分离',
    stages: ['preparing', 'source_separation'],
  },
  {
    id: 'speech_recognition',
    label: '说话人识别与转写',
    stages: ['speaker_diarization', 'asr_transcription'],
  },
  {
    id: 'translation',
    label: '翻译',
    stages: ['translation'],
  },
  {
    id: 'voice_clone_tts',
    label: '语音合成',
    stages: ['voice_clone_tts'],
  },
  {
    id: 'mixing',
    label: '对齐与混音',
    stages: ['temporal_alignment', 'final_mixing'],
  },
]

const ALL_STAGES: PipelineStage[] = [
  'uploaded',
  'preparing',
  'source_separation',
  'speaker_diarization',
  'asr_transcription',
  'translation',
  'voice_clone_tts',
  'temporal_alignment',
  'final_mixing',
]

type StepStatus = 'completed' | 'active' | 'paused' | 'failed' | 'pending'

interface PipelineProgressProps {
  currentStage: PipelineStage | string | null
  progressPercent: number
  stageProgressPercent?: number | null
  etaSeconds?: number | null
  taskStatus: string
}

const STAGE_PROGRESS_RANGES: Record<PipelineStage, { start: number; end: number }> = {
  uploaded: { start: 0, end: 2 },
  preparing: { start: 2, end: 10 },
  source_separation: { start: 10, end: 25 },
  speaker_diarization: { start: 25, end: 45 },
  asr_transcription: { start: 45, end: 65 },
  translation: { start: 65, end: 80 },
  voice_clone_tts: { start: 80, end: 90 },
  temporal_alignment: { start: 90, end: 95 },
  final_mixing: { start: 95, end: 100 },
}

function getStepStatus(
  step: typeof PIPELINE_STEPS[number],
  currentStage: PipelineStage | string | null,
  taskStatus: string
): StepStatus {
  if (taskStatus === 'failed' || taskStatus === 'paused') {
    if (!currentStage) {
      return 'pending'
    }

    const currentIdx = ALL_STAGES.indexOf(currentStage as PipelineStage)
    const stepFirstStageIdx = ALL_STAGES.indexOf(step.stages[0])
    const stepLastStageIdx = ALL_STAGES.indexOf(step.stages[step.stages.length - 1])

    if (currentIdx > stepLastStageIdx) {
      return 'completed'
    }
    if (currentIdx >= stepFirstStageIdx && currentIdx <= stepLastStageIdx) {
      return taskStatus === 'paused' ? 'paused' : 'failed'
    }
    return 'pending'
  }

  if (taskStatus === 'completed') {
    return 'completed'
  }

  if (!currentStage) {
    return 'pending'
  }

  const currentIdx = ALL_STAGES.indexOf(currentStage as PipelineStage)
  if (currentIdx === -1) {
    return 'pending'
  }

  const stepFirstStageIdx = ALL_STAGES.indexOf(step.stages[0])
  const stepLastStageIdx = ALL_STAGES.indexOf(step.stages[step.stages.length - 1])

  if (currentIdx > stepLastStageIdx) {
    return 'completed'
  }
  if (currentIdx >= stepFirstStageIdx && currentIdx <= stepLastStageIdx) {
    return 'active'
  }
  return 'pending'
}

function getActiveStageProgress(currentStage: PipelineStage | string | null, progressPercent: number): number {
  const range = currentStage ? STAGE_PROGRESS_RANGES[currentStage as PipelineStage] : null
  if (!range) {
    return Math.min(Math.max(Math.round(progressPercent), 0), 100)
  }

  const span = range.end - range.start
  if (span <= 0) {
    return progressPercent >= range.end ? 100 : 0
  }

  const boundedOverall = Math.min(Math.max(progressPercent, range.start), range.end)
  return Math.min(Math.max(Math.round(((boundedOverall - range.start) * 100) / span), 0), 100)
}

function getStepStatusLabel(status: StepStatus, progressPercent: number): string {
  switch (status) {
    case 'completed':
      return '已完成'
    case 'active':
      return `进行中 ${progressPercent}%`
    case 'failed':
      return '失败'
    case 'paused':
      return '已暂停'
    case 'pending':
    default:
      return '等待中'
  }
}

function formatEta(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) {
    return '估算中'
  }

  const bounded = Math.max(0, Math.round(seconds))
  if (bounded < 60) {
    return '<1 分钟'
  }

  const minutes = Math.round(bounded / 60)
  if (minutes < 60) {
    return `${minutes} 分钟`
  }

  const hours = Math.floor(minutes / 60)
  const restMinutes = minutes % 60
  return restMinutes ? `${hours} 小时 ${restMinutes} 分钟` : `${hours} 小时`
}

export function PipelineProgress({
  currentStage,
  progressPercent,
  stageProgressPercent,
  etaSeconds,
  taskStatus,
}: PipelineProgressProps) {
  const activeStageProgress = stageProgressPercent ?? getActiveStageProgress(currentStage, progressPercent)

  return (
    <div className="pipeline-progress">
      <div className="pipeline-progress__steps">
        {PIPELINE_STEPS.map((step) => {
          const status = getStepStatus(step, currentStage, taskStatus)

          return (
            <div
              key={step.id}
              className={`pipeline-step pipeline-step--${status}`}
              id={`pipeline-step-${step.id}`}
            >
              <div className={`pipeline-step__icon pipeline-step__icon--${status}`}>
                {status === 'completed' && <Check className="pipeline-step__icon-svg" />}
                {status === 'active' && <Loader2 className="pipeline-step__icon-svg pipeline-step__icon-svg--spin" />}
                {status === 'failed' && <XCircle className="pipeline-step__icon-svg" />}
                {status === 'paused' && <PauseCircle className="pipeline-step__icon-svg" />}
                {status === 'pending' && <Circle className="pipeline-step__icon-svg" />}
              </div>

              <span className="pipeline-step__label">{step.label}</span>
              <span className={`pipeline-step__status pipeline-step__status--${status}`}>
                {getStepStatusLabel(status, activeStageProgress)}
              </span>
            </div>
          )
        })}
      </div>

      <div className="pipeline-progress__bar-container">
        <div className="pipeline-progress__bar-track">
          <div
            className="pipeline-progress__bar-fill"
            style={{ width: `${Math.min(progressPercent, 100)}%` }}
          />
        </div>

        <div className="pipeline-progress__bar-labels">
          <span className="pipeline-progress__bar-percent">总进度 {progressPercent}%</span>
          <span className="pipeline-progress__bar-eta">
            {taskStatus === 'processing' ? `预计剩余 ${formatEta(etaSeconds)}` : ''}
          </span>
        </div>
      </div>
    </div>
  )
}
