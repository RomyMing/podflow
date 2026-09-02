'use client'

import { useCallback, useEffect, useState } from 'react'
import { useToastStore } from '@/stores/toast-store'
import { Toast } from '@/types/ui'
import './toast.css'

/* ── 图标 SVG ── */
const SuccessIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <circle cx="10" cy="10" r="10" fill="#16A34A" fillOpacity="0.12" />
    <path d="M6 10.5l2.5 2.5 5.5-5.5" stroke="#16A34A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

const ErrorIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <circle cx="10" cy="10" r="10" fill="#DC2626" fillOpacity="0.12" />
    <path d="M7 7l6 6M13 7l-6 6" stroke="#DC2626" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
)

const WarningIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <circle cx="10" cy="10" r="10" fill="#F59E0B" fillOpacity="0.12" />
    <path d="M10 6v4.5M10 13.5v.5" stroke="#F59E0B" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
)

const InfoIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <circle cx="10" cy="10" r="10" fill="#2563EB" fillOpacity="0.12" />
    <path d="M10 9v5M10 6.5v.5" stroke="#2563EB" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
)

const CloseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
)

const icons = {
  success: <SuccessIcon />,
  error: <ErrorIcon />,
  warning: <WarningIcon />,
  info: <InfoIcon />,
}

/* ── 单条 Toast 项，带进场/退场动画 ── */
function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
  const [exiting, setExiting] = useState(false)

  const handleClose = useCallback(() => {
    setExiting(true)
    setTimeout(() => onRemove(toast.id), 260)
  }, [onRemove, toast.id])

  useEffect(() => {
    if (toast.duration && toast.duration > 0) {
      const timer = setTimeout(() => handleClose(), toast.duration - 300)
      return () => clearTimeout(timer)
    }
  }, [handleClose, toast.duration])

  return (
    <div
      className={`toast-item toast-item--${toast.type}${exiting ? ' toast-item--exit' : ''}`}
      role="alert"
      aria-live="polite"
    >
      {/* 左侧色条 */}
      <div className="toast-bar" />

      {/* 图标 */}
      <div className="toast-icon">{icons[toast.type]}</div>

      {/* 消息文本 */}
      <div className="toast-message">{toast.message}</div>

      {/* 关闭按钮 */}
      {toast.dismissible !== false && (
        <button className="toast-close" onClick={handleClose} aria-label="关闭">
          <CloseIcon />
        </button>
      )}
    </div>
  )
}

/* ── Toast 容器 + Provider ── */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { toasts, removeToast } = useToastStore()

  return (
    <>
      {children}
      <div className="toast-container" aria-label="通知区域">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
        ))}
      </div>
    </>
  )
}
