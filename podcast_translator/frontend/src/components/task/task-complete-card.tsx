'use client'

import React from 'react'
import { Download, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { AudioPlayer } from '@/components/player/audio-player'

interface TaskCompleteCardProps {
  audioUrl: string
  taskId: string
  onDownload?: () => void
  onViewTranscript?: () => void
}

export function TaskCompleteCard({ audioUrl, taskId, onDownload, onViewTranscript }: TaskCompleteCardProps) {
  const handleDownload = () => {
    if (onDownload) {
      onDownload()
      return
    }

    const link = document.createElement('a')
    link.href = audioUrl
    link.download = `podflow-${taskId.slice(0, 8)}.mp3`
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="task-complete-card" id="task-complete-section">
      <AudioPlayer src={audioUrl} />

      <div className="task-complete-card__actions">
        <Button
          variant="primary"
          size="lg"
          leftIcon={<Download className="w-4 h-4" />}
          onClick={handleDownload}
          id="task-download-btn"
          className="task-complete-card__download-btn"
        >
          下载音频
        </Button>

        <Button
          variant="secondary"
          size="lg"
          leftIcon={<FileText className="w-4 h-4" />}
          onClick={onViewTranscript}
          id="task-transcript-btn"
          className="task-complete-card__transcript-btn"
        >
          查看双语对照
        </Button>
      </div>
    </div>
  )
}
