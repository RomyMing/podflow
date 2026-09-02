'use client'

import { useCallback, useRef, useState } from 'react'
import { TaskService } from '@/services/task-service'
import { TaskConfig, TaskResponse } from '@/types/api'
import { UploadStatus } from '@/types/ui'

const ALLOWED_TYPES = [
  'audio/mpeg',
  'audio/wav',
  'audio/x-wav',
  'audio/mp4',
  'audio/x-m4a',
  'audio/aac',
]

const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac']
const MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024

export interface UseFileUploadReturn {
  status: UploadStatus
  file: File | null
  progress: number
  error: string | null
  selectFile: (file: File) => void
  clearFile: () => void
  upload: (config?: TaskConfig) => Promise<TaskResponse | null>
  cancel: () => void
  validate: (file: File) => string | null
}

export function useFileUpload(): UseFileUploadReturn {
  const [status, setStatus] = useState<UploadStatus>('idle')
  const [file, setFile] = useState<File | null>(null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const validate = useCallback((inputFile: File): string | null => {
    const ext = '.' + inputFile.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `不支持的文件格式 "${ext}"，请上传 MP3、WAV、M4A 或 AAC 音频文件。`
    }

    if (inputFile.type && !ALLOWED_TYPES.includes(inputFile.type)) {
      console.warn(`MIME type mismatch: ${inputFile.type}, but extension is valid`)
    }

    if (inputFile.size > MAX_FILE_SIZE) {
      const sizeMB = Math.round(inputFile.size / 1024 / 1024)
      return `文件大小 ${sizeMB}MB 超过限制，当前上限为 5GB。`
    }

    if (inputFile.size === 0) {
      return '文件为空，请重新选择有效的音频文件。'
    }

    return null
  }, [])

  const selectFile = useCallback((inputFile: File) => {
    const validationError = validate(inputFile)
    if (validationError) {
      setError(validationError)
      setStatus('error')
      return
    }

    setFile(inputFile)
    setError(null)
    setStatus('selecting')
  }, [validate])

  const clearFile = useCallback(() => {
    setFile(null)
    setProgress(0)
    setError(null)
    setStatus('idle')

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }, [])

  const upload = useCallback(async (config?: TaskConfig): Promise<TaskResponse | null> => {
    if (!file) {
      setError('请先选择文件')
      return null
    }

    setStatus('uploading')
    setProgress(0)
    setError(null)

    try {
      const result = await TaskService.createTask(file, config, (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setProgress(percent)
        }
      })

      setStatus('processing')
      setProgress(100)
      return result
    } catch (err: unknown) {
      const axiosErr = err as {
        name?: string
        code?: string
        response?: { data?: { detail?: string } }
        message?: string
      }

      if (axiosErr.name === 'CanceledError' || axiosErr.code === 'ERR_CANCELED') {
        setError('上传已取消')
        setStatus('idle')
      } else {
        const message = axiosErr.response?.data?.detail || axiosErr.message || '上传失败，请稍后重试。'
        setError(message)
        setStatus('error')
      }

      return null
    }
  }, [file])

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setStatus('idle')
    setProgress(0)
  }, [])

  return {
    status,
    file,
    progress,
    error,
    selectFile,
    clearFile,
    upload,
    cancel,
    validate,
  }
}
