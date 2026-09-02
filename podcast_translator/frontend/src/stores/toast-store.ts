import { create } from 'zustand'
import { Toast, ToastType } from '@/types/ui'

interface ToastState {
  toasts: Toast[]
  showToast: (message: string, type: ToastType, duration?: number) => void
  removeToast: (id: string) => void
  
  // Shortcuts
  success: (message: string, duration?: number) => void
  error: (message: string, duration?: number) => void
  warning: (message: string, duration?: number) => void
  info: (message: string, duration?: number) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  
  showToast: (message, type, duration = 3000) => {
    const id = Math.random().toString(36).substring(2, 9)
    const toast: Toast = { id, message, type, duration, dismissible: true }
    
    set((state) => ({
      toasts: [...state.toasts, toast]
    }))

    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id)
        }))
      }, duration)
    }
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id)
    }))
  },

  success: (msg, d) => useToastStore.getState().showToast(msg, 'success', d),
  error: (msg, d) => useToastStore.getState().showToast(msg, 'error', d),
  warning: (msg, d) => useToastStore.getState().showToast(msg, 'warning', d),
  info: (msg, d) => useToastStore.getState().showToast(msg, 'info', d)
}))
