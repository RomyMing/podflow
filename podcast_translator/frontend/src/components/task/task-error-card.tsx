'use client'

import React from 'react'
import { AlertCircle } from 'lucide-react'
import { formatTaskErrorMessage } from '@/lib/task-display'

interface TaskErrorCardProps {
  errorMessage?: string | null
  currentStage?: string | null
}

const STAGE_LABELS: Record<string, string> = {
  preparing: '准备任务',
  uploaded: '上传入库',
  source_separation: '音源分离',
  speaker_diarization: '说话人分离',
  asr_transcription: '语音转写',
  translation: '翻译',
  voice_clone_tts: '语音合成',
  temporal_alignment: '时序对齐',
  final_mixing: '最终混音',
}

export function TaskErrorCard({ errorMessage, currentStage }: TaskErrorCardProps) {
  const stageText = currentStage ? STAGE_LABELS[currentStage] || '未知阶段' : null
  const description = formatTaskErrorMessage(errorMessage)
    || (stageText ? `${stageText}阶段出现错误，请查看日志后重新创建任务。` : '任务处理过程中出现错误。')

  return (
    <div className="task-error-card" id="task-error-section">
      <div className="task-error-card__icon-wrapper">
        <AlertCircle className="task-error-card__icon" />
      </div>

      <h3 className="task-error-card__title">任务失败</h3>
      <p className="task-error-card__description">{description}</p>
      <p className="task-error-card__hint">失败任务不会占用最终额度，系统会按终态执行退款补偿。</p>
    </div>
  )
}
