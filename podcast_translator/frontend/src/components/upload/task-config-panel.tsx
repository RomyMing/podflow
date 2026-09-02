'use client'

import { useState } from 'react'
import { ChevronDown, FileAudio, Globe, Users, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  getDefaultOutputFormat,
  type OutputFormatPreference,
} from '@/lib/preferences'
import { TaskConfigFormData } from '@/types/ui'

interface TaskConfigPanelProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (config: TaskConfigFormData) => void
  isSubmitting: boolean
  fileName?: string
}

const LANGUAGES = [
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
]

const SPEAKER_OPTIONS = [
  { value: 0, label: '自动检测' },
  { value: 1, label: '1 位' },
  { value: 2, label: '2 位' },
  { value: 3, label: '3 位' },
  { value: 4, label: '4 位' },
]

const FORMAT_OPTIONS: { value: OutputFormatPreference; label: string }[] = [
  { value: 'mp3', label: 'MP3（推荐）' },
  { value: 'wav', label: 'WAV（无损）' },
  { value: 'aac', label: 'AAC' },
]

export function TaskConfigPanel({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  fileName,
}: TaskConfigPanelProps) {
  const [config, setConfig] = useState<TaskConfigFormData>(() => ({
    targetLanguage: 'zh',
    speakerCount: 0,
    outputFormat: getDefaultOutputFormat(),
  }))

  if (!isOpen) {
    return null
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    onSubmit(config)
  }

  return (
    <>
      <div className="config-panel__backdrop" onClick={onClose} />

      <aside className="config-panel" id="task-config-panel">
        <div className="config-panel__header">
          <h2 className="config-panel__title">任务配置</h2>
          <button
            className="config-panel__close"
            onClick={onClose}
            aria-label="关闭配置面板"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {fileName && (
          <div className="config-panel__file">
            <FileAudio className="w-4 h-4 text-text-secondary" />
            <span className="config-panel__file-name">{fileName}</span>
          </div>
        )}

        <form className="config-panel__form" onSubmit={handleSubmit}>
          <div className="config-panel__group">
            <label className="config-panel__label">
              <Globe className="w-4 h-4" />
              目标语言
            </label>
            <div className="config-panel__select-wrapper">
              <select
                className="config-panel__select"
                value={config.targetLanguage}
                onChange={(event) => setConfig({ ...config, targetLanguage: event.target.value })}
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.value} value={lang.value}>
                    {lang.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="config-panel__select-icon" />
            </div>
          </div>

          <div className="config-panel__group">
            <label className="config-panel__label">
              <Users className="w-4 h-4" />
              说话人数
            </label>
            <div className="config-panel__select-wrapper">
              <select
                className="config-panel__select"
                value={config.speakerCount}
                onChange={(event) => setConfig({ ...config, speakerCount: Number(event.target.value) })}
              >
                {SPEAKER_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="config-panel__select-icon" />
            </div>
          </div>

          <div className="config-panel__group">
            <label className="config-panel__label">
              <FileAudio className="w-4 h-4" />
              输出格式
            </label>
            <div className="config-panel__radio-group">
              {FORMAT_OPTIONS.map((fmt) => (
                <label
                  key={fmt.value}
                  className={`config-panel__radio ${
                    config.outputFormat === fmt.value ? 'config-panel__radio--active' : ''
                  }`}
                >
                  <input
                    type="radio"
                    name="outputFormat"
                    value={fmt.value}
                    checked={config.outputFormat === fmt.value}
                    onChange={() => setConfig({ ...config, outputFormat: fmt.value })}
                    className="sr-only"
                  />
                  {fmt.label}
                </label>
              ))}
            </div>
          </div>

          <div className="config-panel__actions">
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={onClose}
              className="flex-1"
            >
              取消
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isSubmitting}
              className="flex-1"
            >
              开始处理
            </Button>
          </div>
        </form>
      </aside>
    </>
  )
}
