import { apiClient } from './api-client'
import {
  ApiKeyProvider,
  QuotaResponse,
  UserApiKeyResponse,
  UserApiKeyUpdateRequest,
  UserResponse,
} from '@/types/api'

export const UserService = {
  /**
   * 获取当前登录用户信息
   */
  async getMe(): Promise<UserResponse> {
    const { data } = await apiClient.get<UserResponse>('/users/me')
    return data
  },

  /**
   * 获取当前用户配额信息
   */
  async getQuota(): Promise<QuotaResponse> {
    const { data } = await apiClient.get<QuotaResponse>('/users/me/quota')
    return data
  },

  async listApiKeys(): Promise<UserApiKeyResponse[]> {
    const { data } = await apiClient.get<UserApiKeyResponse[]>('/users/me/api-keys')
    return data
  },

  async upsertApiKey(
    provider: ApiKeyProvider,
    payload: UserApiKeyUpdateRequest,
  ): Promise<UserApiKeyResponse> {
    const { data } = await apiClient.put<UserApiKeyResponse>(`/users/me/api-keys/${provider}`, payload)
    return data
  },

  async deleteApiKey(provider: ApiKeyProvider): Promise<void> {
    await apiClient.delete(`/users/me/api-keys/${provider}`)
  },

  async verifyApiKey(provider: ApiKeyProvider): Promise<UserApiKeyResponse> {
    const { data } = await apiClient.post<UserApiKeyResponse>(`/users/me/api-keys/${provider}/verify`)
    return data
  }
}
