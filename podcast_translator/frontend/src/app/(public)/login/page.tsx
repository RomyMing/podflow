'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { authMode } from '@/config/app-config'
import { useCountdown } from '@/hooks/useCountdown'
import { AuthService } from '@/services/auth-service'
import { useAuthStore } from '@/stores/auth-store'
import { useToastStore } from '@/stores/toast-store'
import './login.css'

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const redirectUrl = searchParams.get('redirect') || '/'
  const { checkAuth } = useAuthStore()
  const toast = useToastStore()

  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDemoSubmitting, setIsDemoSubmitting] = useState(false)

  const { seconds, isActive, start: startCountdown } = useCountdown(60)

  const handleSendCode = async () => {
    if (!phone) {
      toast.error('请输入手机号')
      return
    }

    if (!/^1[3-9]\d{9}$/.test(phone)) {
      toast.error('手机号格式不正确')
      return
    }

    try {
      setIsSending(true)
      await AuthService.sendSms(phone)
      toast.success('验证码已发送')
      startCountdown()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '验证码发送失败')
    } finally {
      setIsSending(false)
    }
  }

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()

    if (!agreed) {
      toast.error('请先确认当前为内测版本')
      return
    }

    if (!phone || !code) {
      toast.error('请填写手机号和验证码')
      return
    }

    try {
      setIsSubmitting(true)
      await AuthService.loginSms(phone, code)
      await checkAuth()
      toast.success('登录成功')
      router.push(redirectUrl)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '登录失败，请检查验证码')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDemoLogin = async () => {
    try {
      setIsDemoSubmitting(true)
      await AuthService.loginDemo()
      await checkAuth()
      toast.success('已进入演示环境')
      router.push(redirectUrl)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '进入演示环境失败，请稍后重试')
    } finally {
      setIsDemoSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-bg">
        <div className="login-glow login-glow-1" />
        <div className="login-glow login-glow-2" />
      </div>

      <div className="login-card">
        <div className="login-logo">
          <h1 className="login-logo-text">播客翻译</h1>
        </div>

        {authMode === 'demo' ? (
          <>
            <p className="login-subtitle">
              这是用于作品集展示的演示环境。点击下方按钮即可进入共享 Demo 账号，快速体验上传、进度跟踪和结果播放流程。
            </p>

            <div className="demo-login-panel">
              <div className="demo-login-panel__eyebrow">Portfolio Demo</div>
              <h2 className="demo-login-panel__title">一键进入项目体验</h2>
              <p className="demo-login-panel__text">
                当前环境默认走演示链路，适合给访客快速浏览任务流和成品效果，不需要短信验证码。
              </p>
              <button
                type="button"
                className="btn-login"
                disabled={isDemoSubmitting}
                onClick={handleDemoLogin}
              >
                {isDemoSubmitting && (
                  <svg className="btn-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4m-3.93 7.07l-2.83-2.83M7.76 7.76L4.93 4.93" />
                  </svg>
                )}
                进入演示环境
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="login-subtitle">
              使用手机号登录，开始上传本地音频并跟踪任务处理进度。
            </p>

            <form className="login-form" onSubmit={handleLogin}>
              <div className="form-group">
                <label className="form-label">手机号</label>
                <input
                  type="tel"
                  className="form-input"
                  placeholder="请输入 11 位手机号"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  maxLength={11}
                />
              </div>

              <div className="form-group">
                <label className="form-label">验证码</label>
                <div className="form-row">
                  <input
                    type="text"
                    className="form-input"
                    placeholder="6 位验证码"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    maxLength={6}
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="btn-send-code"
                    onClick={handleSendCode}
                    disabled={isActive || isSending}
                  >
                    {isSending ? '发送中...' : isActive ? `${seconds}s` : '发送验证码'}
                  </button>
                </div>
              </div>

              <div className="form-agreement">
                <input
                  type="checkbox"
                  id="agree"
                  checked={agreed}
                  onChange={(event) => setAgreed(event.target.checked)}
                  className="form-checkbox"
                />
                <label htmlFor="agree" className="form-agreement-text">
                  我已知晓当前内测版本仅覆盖短信登录、本地上传、任务进度和结果下载这条主链路。
                </label>
              </div>

              <button
                type="submit"
                className="btn-login"
                disabled={isSubmitting}
              >
                {isSubmitting && (
                  <svg className="btn-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4m-3.93 7.07l-2.83-2.83M7.76 7.76L4.93 4.93" />
                  </svg>
                )}
                登录 / 注册
              </button>

              <div className="login-divider">
                <span>当前仅开放短信登录</span>
              </div>
            </form>
          </>
        )}

        <p className="login-footer">&copy; 2026 播客翻译. All rights reserved.</p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginContent />
    </Suspense>
  )
}
