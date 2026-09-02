'use client'

import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // 可在此接入 Sentry 等监控服务
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <div className="error-boundary">
          <div className="error-boundary__icon" aria-hidden="true">⚠️</div>
          <p className="error-boundary__title">出了点问题</p>
          <p className="error-boundary__desc">
            页面渲染时发生了意料之外的错误，请刷新页面重试。
          </p>
          <button
            className="error-boundary__reload"
            onClick={() => this.setState({ hasError: false, error: undefined })}
            id="error-boundary-retry"
          >
            重新加载
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
