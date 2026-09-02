import { apiClient } from './api-client'
import { TokenResponse } from '@/types/api'
import { setTokens, clearTokens } from '@/lib/auth'

export const AuthService = {
  /**
   * 发送短信验证码
   */
  async sendSms(phone: string): Promise<{ message: string }> {
    const { data } = await apiClient.post('/auth/sms/send', { phone })
    return data
  },

  /**
   * 短信登录
   */
  async loginSms(phone: string, code: string): Promise<TokenResponse> {
    const { data } = await apiClient.post<TokenResponse>('/auth/sms/login', { phone, code })
    setTokens(data.access_token, data.refresh_token)
    return data
  },

  async loginDemo(): Promise<TokenResponse> {
    const { data } = await apiClient.post<TokenResponse>('/auth/demo/login')
    setTokens(data.access_token, data.refresh_token)
    return data
  },

  /**
   * 微信登录
   */
  async loginWechat(code: string): Promise<TokenResponse> {
    const { data } = await apiClient.post<TokenResponse>('/auth/wechat/login', { code })
    setTokens(data.access_token, data.refresh_token)
    return data
  },

  /**
   * 退出登录
   */
  logout() {
    clearTokens()
    window.location.href = '/login'
  }
}
