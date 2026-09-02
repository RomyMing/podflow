const API_V1_BASE_PATH = '/api/v1'
const DEFAULT_DEV_BACKEND_ORIGIN = 'http://127.0.0.1:8080'

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '')

const toApiBaseUrl = (originOrBaseUrl: string): string => {
  const normalized = trimTrailingSlash(originOrBaseUrl.trim())

  if (!normalized) {
    return API_V1_BASE_PATH
  }

  if (normalized.endsWith(API_V1_BASE_PATH)) {
    return normalized
  }

  if (/^https?:\/\//.test(normalized)) {
    return `${normalized}${API_V1_BASE_PATH}`
  }

  return normalized
}

const apiOrigin = process.env.NEXT_PUBLIC_PCT_API_ORIGIN
const uploadApiOrigin = process.env.NEXT_PUBLIC_PCT_UPLOAD_API_ORIGIN ?? apiOrigin

const defaultDevApiBaseUrl = toApiBaseUrl(DEFAULT_DEV_BACKEND_ORIGIN)

export const apiBaseUrl =
  apiOrigin
    ? toApiBaseUrl(apiOrigin)
    : process.env.NODE_ENV === 'development'
      ? defaultDevApiBaseUrl
      : API_V1_BASE_PATH

export const uploadApiBaseUrl =
  uploadApiOrigin
    ? toApiBaseUrl(uploadApiOrigin)
    : process.env.NODE_ENV === 'development'
      ? defaultDevApiBaseUrl
      : apiBaseUrl

const toWebSocketOrigin = (originOrBaseUrl: string): string => {
  const normalized = trimTrailingSlash(originOrBaseUrl.trim())
  if (!normalized) {
    return ''
  }

  return normalized
    .replace(/\/api\/v1$/i, '')
    .replace(/^http:\/\//i, 'ws://')
    .replace(/^https:\/\//i, 'wss://')
}

export const websocketBaseUrl =
  uploadApiOrigin || apiOrigin
    ? toWebSocketOrigin(uploadApiOrigin ?? apiOrigin ?? '')
    : process.env.NODE_ENV === 'development'
      ? toWebSocketOrigin(DEFAULT_DEV_BACKEND_ORIGIN)
      : ''

export const joinApiPath = (baseUrl: string | undefined, path: string): string => {
  const normalizedBase = trimTrailingSlash(baseUrl || apiBaseUrl)
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}
