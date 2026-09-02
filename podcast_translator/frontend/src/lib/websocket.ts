import { getAccessToken } from './auth'
import { websocketBaseUrl } from '@/services/api-base-url'

import { WSProgressMessage } from '@/types/api'

type WSCallback = (msg: WSProgressMessage) => void

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY_MS = 1500
const NON_RETRYABLE_CLOSE_CODES = new Set([1000, 4001, 4003, 4004])

export class TaskWebSocket {
  private ws: WebSocket | null = null
  private readonly taskId: string
  private readonly url: string
  private onMessageCb: WSCallback | null = null
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private manuallyClosed = false

  constructor(taskId: string) {
    this.taskId = taskId
    if (websocketBaseUrl) {
      this.url = `${websocketBaseUrl}/api/v1/tasks/${taskId}/ws`
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.url = `${protocol}//${host}/api/v1/tasks/${taskId}/ws`
  }

  public connect(onMessage: WSCallback) {
    this.onMessageCb = onMessage
    this.manuallyClosed = false
    this.openSocket()
  }

  private openSocket() {
    const token = getAccessToken()
    if (!token) {
      return
    }

    this.ws = new WebSocket(`${this.url}?token=${token}`)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSProgressMessage
        this.onMessageCb?.(data)
      } catch (err) {
        console.error('Failed to parse task websocket message', err)
      }
    }

    this.ws.onerror = () => {
      // 浏览器的 WebSocket error 事件几乎不暴露可诊断细节。
      // 将真正的诊断信息统一放到 onclose 里，避免控制台只出现无意义噪音。
    }

    this.ws.onclose = (event) => {
      this.ws = null
      if (this.manuallyClosed) {
        return
      }

      if (event.code !== 1000) {
        console.warn(
          `Task websocket closed for ${this.taskId} (code=${event.code}, reason=${event.reason || 'n/a'})`
        )
      }

      if (NON_RETRYABLE_CLOSE_CODES.has(event.code)) {
        return
      }

      if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        return
      }

      this.reconnectAttempts += 1
      this.reconnectTimer = setTimeout(() => {
        this.openSocket()
      }, RECONNECT_DELAY_MS)
    }
  }

  public disconnect() {
    this.manuallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
