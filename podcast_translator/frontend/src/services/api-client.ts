import axios, {
  AxiosError,
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios'
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from '@/lib/auth'
import { TokenResponse } from '@/types/api'

import { apiBaseUrl, joinApiPath, uploadApiBaseUrl } from './api-base-url'

// ============================================================
// Axios Configuration
// ============================================================

const createApiClient = (baseURL: string): AxiosInstance =>
  axios.create({
    baseURL,
    timeout: 7200000, // 120 minutes timeout to support large files
    headers: {
      'Content-Type': 'application/json',
    },
  })

export const apiClient = createApiClient(apiBaseUrl)
export const uploadApiClient = createApiClient(uploadApiBaseUrl)

// ============================================================
// Request Interceptor
// ============================================================

const attachAuthInterceptors = (client: AxiosInstance) => {
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = getAccessToken()
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    },
    (error) => Promise.reject(error)
  )

  client.interceptors.response.use(
    (response: AxiosResponse) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined

      if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
        if (isRefreshing) {
          return new Promise(function (resolve, reject) {
            failedQueue.push({ resolve, reject })
          })
            .then((token) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = 'Bearer ' + token
              }
              return client(originalRequest)
            })
            .catch((err) => {
              return Promise.reject(err)
            })
        }

        originalRequest._retry = true
        isRefreshing = true

        const refreshToken = getRefreshToken()
        if (!refreshToken) {
          processQueue(new Error('登录状态已过期，请重新登录。'))
          clearTokens()
          window.location.href = '/login'
          return Promise.reject(error)
        }

        try {
          const refreshUrl = joinApiPath(
            (originalRequest.baseURL as string | undefined) ?? client.defaults.baseURL,
            '/auth/refresh'
          )
          const { data } = await axios.post<TokenResponse>(refreshUrl, {
            refresh_token: refreshToken,
          })

          setTokens(data.access_token, data.refresh_token)
          processQueue(null, data.access_token)

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = 'Bearer ' + data.access_token
          }

          return client(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError as Error, null)
          clearTokens()
          window.location.href = '/login'
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      }

      return Promise.reject(error)
    }
  )
}

// ============================================================
// Response Interceptor (Token Refresh Logic)
// ============================================================

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: unknown) => void
  reject: (reason?: unknown) => void
}> = []

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

attachAuthInterceptors(apiClient)
attachAuthInterceptors(uploadApiClient)

// ============================================================
// Error message helper
// ============================================================

/**
 * 从后端响应中提取可读的错误信息（FastAPI 的 `detail` 字段），
 * 避免直接显示 axios 的通用 "Request failed with status code 4xx"。
 */
export function getApiErrorMessage(error: unknown, fallback = '操作失败，请稍后重试。'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI 校验错误数组
      const first = detail[0] as { msg?: string }
      if (first?.msg) {
        return first.msg
      }
    }
    if (error.message) {
      return error.message
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}
