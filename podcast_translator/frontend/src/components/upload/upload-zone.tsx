'use client'

import { useCallback, useRef, useState } from 'react'
import { FileAudio, Loader2, UploadCloud, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface UploadZoneProps {
  onFileSelect: (file: File) => void
  selectedFile: File | null
  onClear: () => void
  isUploading: boolean
  uploadProgress: number
  error: string | null
  validate: (file: File) => string | null
}

export function UploadZone({
  onFileSelect,
  selectedFile,
  onClear,
  isUploading,
  uploadProgress,
  error,
}: UploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragOver(false)

    const files = event.dataTransfer.files
    if (files.length > 0) {
      onFileSelect(files[0])
    }
  }, [onFileSelect])

  const handleClick = useCallback(() => {
    if (!isUploading) {
      fileInputRef.current?.click()
    }
  }, [isUploading])

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (files && files.length > 0) {
      onFileSelect(files[0])
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [onFileSelect])

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) {
      return `${bytes} B`
    }
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div
      id="upload-zone"
      className={cn(
        'upload-zone',
        isDragOver && 'upload-zone--drag-over',
        selectedFile && !error && 'upload-zone--has-file',
        isUploading && 'upload-zone--uploading',
        error && 'upload-zone--error',
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-label="上传音频文件"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".mp3,.wav,.m4a,.aac,audio/*"
        onChange={handleFileChange}
        className="hidden"
        aria-hidden="true"
      />

      {isUploading && (
        <div className="upload-zone__uploading">
          <Loader2 className="upload-zone__spinner" />
          <p className="upload-zone__text">上传中... {uploadProgress}%</p>
          <div className="upload-zone__progress-track">
            <div
              className="upload-zone__progress-fill"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {!isUploading && selectedFile && !error && (
        <div className="upload-zone__selected">
          <FileAudio className="upload-zone__file-icon" />
          <div className="upload-zone__file-info">
            <p className="upload-zone__filename">{selectedFile.name}</p>
            <p className="upload-zone__filesize">{formatFileSize(selectedFile.size)}</p>
          </div>
          <button
            className="upload-zone__clear"
            onClick={(event) => {
              event.stopPropagation()
              onClear()
            }}
            aria-label="移除文件"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {!isUploading && !selectedFile && !error && (
        <div className="upload-zone__default">
          <UploadCloud className="upload-zone__icon" />
          <p className="upload-zone__text">
            拖拽音频文件到这里，或 <span className="upload-zone__link">点击选择文件</span>
          </p>
          <p className="upload-zone__caption">支持 MP3 / WAV / M4A / AAC，单文件上限 5GB。</p>
        </div>
      )}

      {!isUploading && error && (
        <div className="upload-zone__error">
          <FileAudio className="upload-zone__file-icon upload-zone__file-icon--error" />
          <p className="upload-zone__error-text">{error}</p>
          <p className="upload-zone__caption">点击重新选择文件</p>
        </div>
      )}
    </div>
  )
}
