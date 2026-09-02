'use client'

import Link from 'next/link'
import { useCallback, useState } from 'react'
import { useRouter } from 'next/navigation'
import { allowUserUpload, enableSampleTasks, isDemoExperience } from '@/config/app-config'
import { TaskList } from '@/components/task/task-list'
import { QuotaBar } from '@/components/upload/quota-bar'
import { TaskConfigPanel } from '@/components/upload/task-config-panel'
import { UploadZone } from '@/components/upload/upload-zone'
import { useFileUpload } from '@/hooks/useFileUpload'
import {
  getTranslationProviderPreference,
  getVoiceCloneConsentPreference,
  getVoiceCloneModePreference,
  getVoiceCloneProviderPreference,
} from '@/lib/preferences'
import { useToastStore } from '@/stores/toast-store'
import { useTaskStore } from '@/stores/task-store'
import { TaskConfig } from '@/types/api'
import { TaskConfigFormData } from '@/types/ui'
import './home.css'

export default function HomePage() {
  const router = useRouter()
  const toast = useToastStore()
  const { fetchTasks } = useTaskStore()
  const {
    status,
    file,
    progress,
    error,
    selectFile,
    clearFile,
    upload,
    validate,
  } = useFileUpload()

  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleFileSelect = useCallback((selectedFile: File) => {
    if (!allowUserUpload) {
      return
    }

    selectFile(selectedFile)
    const validationError = validate(selectedFile)
    if (!validationError) {
      setIsConfigOpen(true)
    }
  }, [selectFile, validate])

  const handleConfigSubmit = useCallback(async (formData: TaskConfigFormData) => {
    setIsSubmitting(true)
    const voiceCloneMode = getVoiceCloneModePreference()
    const voiceCloneConsentConfirmed = getVoiceCloneConsentPreference()

    if (voiceCloneMode !== 'off' && !voiceCloneConsentConfirmed) {
      setIsSubmitting(false)
      setIsConfigOpen(false)
      toast.info('请先在个人中心确认声纹克隆授权，再创建任务。', 5000)
      router.push('/profile')
      return
    }

    const config: TaskConfig = {
      target_language: formData.targetLanguage,
      speaker_count: formData.speakerCount,
      output_format: formData.outputFormat,
      translation_provider: getTranslationProviderPreference(),
      voice_clone_provider: getVoiceCloneProviderPreference(),
      voice_clone_mode: voiceCloneMode,
      voice_clone_consent_confirmed: voiceCloneConsentConfirmed,
    }

    const result = await upload(config)
    setIsSubmitting(false)

    if (!result) {
      return
    }

    setIsConfigOpen(false)
    toast.info('文件已上传，任务已进入处理队列。请以任务详情页的最终状态为准。', 5000)
    fetchTasks(0, 5)
    router.push(`/tasks/${result.id}`)
  }, [fetchTasks, router, toast, upload])

  return (
    <div className="home-page">
      <section className="hero">
        <h1 className="hero__title">把英文播客翻成中文</h1>
        <p className="hero__subtitle">
          当前版本聚焦一条端到端主链路：本地音频上传、异步处理、实时进度和结果播放下载。
        </p>
      </section>

      {(isDemoExperience || enableSampleTasks) && (
        <section className="demo-quickstart">
          <div>
            <p className="demo-quickstart__eyebrow">Portfolio Demo</p>
            <h2 className="demo-quickstart__title">先看示例，再决定是否动手体验</h2>
            <p className="demo-quickstart__text">
              这个环境用于作品集展示。你可以直接查看现有任务样例，也可以根据当前环境配置上传自己的音频体验完整流程。
            </p>
          </div>
          <div className="demo-quickstart__actions">
            <Link href="/tasks" className="demo-quickstart__link">
              查看任务历史
            </Link>
            <span className="demo-quickstart__hint">
              {allowUserUpload ? '也支持直接上传音频创建新任务。' : '当前环境已关闭上传，仅开放示例浏览。'}
            </span>
          </div>
        </section>
      )}

      {allowUserUpload ? (
        <>
          <UploadZone
            onFileSelect={handleFileSelect}
            selectedFile={file}
            onClear={clearFile}
            isUploading={status === 'uploading'}
            uploadProgress={progress}
            error={error}
            validate={validate}
          />

          <div className="home-divider">
            <span>当前仅支持本地音频文件上传，URL 导入暂未开放。</span>
          </div>
        </>
      ) : (
        <div className="home-divider">
          <span>当前展示环境已关闭上传能力，请前往任务历史查看示例任务。</span>
        </div>
      )}

      <QuotaBar />
      <TaskList maxItems={5} />

      {allowUserUpload && (
        <TaskConfigPanel
          isOpen={isConfigOpen}
          onClose={() => setIsConfigOpen(false)}
          onSubmit={handleConfigSubmit}
          isSubmitting={isSubmitting}
          fileName={file?.name}
        />
      )}
    </div>
  )
}
