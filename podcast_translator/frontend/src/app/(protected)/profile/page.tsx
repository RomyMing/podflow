'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle, KeyRound, Trash2 } from 'lucide-react'
import { Toggle } from '@/components/ui/toggle'
import { ProgressBar } from '@/components/ui/progress-bar'
import {
  LS_NOTIFY_KEY,
  getDefaultOutputFormat,
  getTranslationProviderPreference,
  getVoiceCloneConsentPreference,
  getVoiceCloneModePreference,
  getVoiceCloneProviderPreference,
  setDefaultOutputFormat as saveDefaultOutputFormat,
  setTranslationProviderPreference,
  setVoiceCloneConsentPreference,
  setVoiceCloneModePreference,
  setVoiceCloneProviderPreference,
  type OutputFormatPreference,
  type TranslationProviderPreference,
  type VoiceCloneModePreference,
  type VoiceCloneProviderPreference,
} from '@/lib/preferences'
import { getApiErrorMessage } from '@/services/api-client'
import { UserService } from '@/services/user-service'
import { useAuthStore } from '@/stores/auth-store'
import { ApiKeyProvider, QuotaResponse, UserApiKeyResponse } from '@/types/api'
import './profile.css'

const API_PROVIDERS: Array<{
  key: ApiKeyProvider
  label: string
  placeholder: string
  description?: string
  supportsBaseUrl?: boolean
  supportsRegion?: boolean
  helpUrl?: string
  helpSteps?: string[]
}> = [
  {
    key: 'dashscope',
    label: 'DashScope（阿里云百炼）',
    placeholder: 'sk-...',
    description: 'CosyVoice 语音合成（fallback TTS）使用这个密钥。',
    helpUrl: 'https://bailian.console.aliyun.com/?apiKey=1#/api-key',
    helpSteps: [
      '登录阿里云百炼控制台 bailian.console.aliyun.com',
      '右上角头像 →「API-KEY」→ 创建我的 API-KEY',
      '复制以 sk- 开头的密钥粘贴到这里',
      '确保已开通「百炼/语音合成 CosyVoice」服务',
    ],
  },
  {
    key: 'openai',
    label: 'OpenAI',
    placeholder: 'sk-...',
    description: '可选的翻译 Provider（默认用 DeepSeek）。',
    helpUrl: 'https://platform.openai.com/api-keys',
    helpSteps: [
      '登录 platform.openai.com',
      '左侧「API keys」→ Create new secret key',
      '复制以 sk- 开头的密钥粘贴到这里',
    ],
  },
  {
    key: 'deepseek',
    label: 'DeepSeek',
    placeholder: 'sk-...',
    description: '文本翻译默认使用这个密钥。',
    helpUrl: 'https://platform.deepseek.com/api_keys',
    helpSteps: [
      '登录 platform.deepseek.com',
      '左侧「API keys」→ 创建 API key',
      '复制以 sk- 开头的密钥粘贴到这里',
      '确保账户有可用余额',
    ],
  },
  {
    key: 'huggingface',
    label: 'Hugging Face',
    placeholder: 'hf_...',
    description: '说话人识别（pyannote）需要这个访问令牌。',
    supportsBaseUrl: false,
    supportsRegion: false,
    helpUrl: 'https://huggingface.co/settings/tokens',
    helpSteps: [
      '登录 huggingface.co → Settings → Access Tokens',
      'New token，类型选 Read，生成以 hf_ 开头的令牌',
      '⚠️ 必须在模型页接受访问条款：pyannote/speaker-diarization-3.1 与 pyannote/segmentation-3.0',
      '复制令牌粘贴到这里',
    ],
  },
  {
    key: 'elevenlabs',
    label: 'ElevenLabs',
    placeholder: 'sk_...',
    description: '商业级声纹克隆与主 TTS 使用这个密钥。',
    supportsBaseUrl: false,
    supportsRegion: false,
    helpUrl: 'https://elevenlabs.io/app/settings/api-keys',
    helpSteps: [
      '登录 elevenlabs.io → 右上角头像 → API Keys',
      'Create API Key，复制密钥（通常以 sk_ 开头）粘贴到这里',
      '确保套餐额度足够（声纹克隆按字符计费）',
    ],
  },
]

type ApiKeyFormState = Record<ApiKeyProvider, {
  apiKey: string
  baseUrl: string
  region: string
  isSaving: boolean
  message: string | null
}>

function emptyApiForms(): ApiKeyFormState {
  return {
    dashscope: { apiKey: '', baseUrl: '', region: '', isSaving: false, message: null },
    openai: { apiKey: '', baseUrl: '', region: '', isSaving: false, message: null },
    deepseek: { apiKey: '', baseUrl: '', region: '', isSaving: false, message: null },
    huggingface: { apiKey: '', baseUrl: '', region: '', isSaving: false, message: null },
    elevenlabs: { apiKey: '', baseUrl: '', region: '', isSaving: false, message: null },
  }
}

export default function ProfilePage() {
  const router = useRouter()
  const { user, logout } = useAuthStore()
  const [quota, setQuota] = useState<QuotaResponse | null>(null)
  const [notifyOnComplete, setNotifyOnComplete] = useState(false)
  const [defaultFormat, setDefaultFormat] = useState<OutputFormatPreference>('mp3')
  const [translationProvider, setTranslationProvider] = useState<TranslationProviderPreference>('deepseek')
  const [voiceCloneMode, setVoiceCloneMode] = useState<VoiceCloneModePreference>('best_effort')
  const [voiceCloneProvider, setVoiceCloneProvider] = useState<VoiceCloneProviderPreference>('elevenlabs')
  const [voiceCloneConsentConfirmed, setVoiceCloneConsentConfirmed] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [apiKeys, setApiKeys] = useState<UserApiKeyResponse[]>([])
  const [apiForms, setApiForms] = useState<ApiKeyFormState>(() => emptyApiForms())

  useEffect(() => {
    setNotifyOnComplete(localStorage.getItem(LS_NOTIFY_KEY) === 'true')
    setDefaultFormat(getDefaultOutputFormat())
    setTranslationProvider(getTranslationProviderPreference())
    setVoiceCloneMode(getVoiceCloneModePreference())
    setVoiceCloneProvider(getVoiceCloneProviderPreference())
    setVoiceCloneConsentConfirmed(getVoiceCloneConsentPreference())
    UserService.getQuota().then(setQuota).catch(() => {})
    UserService.listApiKeys().then((records) => {
      setApiKeys(records)
      setApiForms((forms) => {
        const next = { ...forms }
        for (const record of records) {
          if (record.provider in next) {
            next[record.provider] = {
              ...next[record.provider],
              baseUrl: record.base_url || '',
              region: record.region || '',
            }
          }
        }
        return next
      })
    }).catch(() => {})
  }, [])

  function handleNotifyToggle(value: boolean) {
    setNotifyOnComplete(value)
    localStorage.setItem(LS_NOTIFY_KEY, String(value))
  }

  function handleFormatChange(format: OutputFormatPreference) {
    setDefaultFormat(format)
    saveDefaultOutputFormat(format)
  }

  function handleTranslationProviderChange(provider: TranslationProviderPreference) {
    setTranslationProvider(provider)
    setTranslationProviderPreference(provider)
  }

  function handleVoiceCloneModeChange(mode: VoiceCloneModePreference) {
    setVoiceCloneMode(mode)
    setVoiceCloneModePreference(mode)
  }

  function handleVoiceCloneProviderChange(provider: VoiceCloneProviderPreference) {
    setVoiceCloneProvider(provider)
    setVoiceCloneProviderPreference(provider)
  }

  function handleVoiceCloneConsentChange(value: boolean) {
    setVoiceCloneConsentConfirmed(value)
    setVoiceCloneConsentPreference(value)
  }

  function handleLogout() {
    logout()
    router.replace('/login')
  }

  function findApiKey(provider: ApiKeyProvider): UserApiKeyResponse | undefined {
    return apiKeys.find((item) => item.provider === provider)
  }

  function updateApiForm(provider: ApiKeyProvider, updates: Partial<ApiKeyFormState[ApiKeyProvider]>) {
    setApiForms((forms) => ({
      ...forms,
      [provider]: {
        ...forms[provider],
        ...updates,
      },
    }))
  }

  async function handleSaveApiKey(provider: ApiKeyProvider) {
    const form = apiForms[provider]
    updateApiForm(provider, { isSaving: true, message: null })
    try {
      const saved = await UserService.upsertApiKey(provider, {
        api_key: form.apiKey || undefined,
        base_url: form.baseUrl || null,
        region: form.region || null,
        enabled: true,
      })
      setApiKeys((records) => [saved, ...records.filter((item) => item.provider !== provider)])
      updateApiForm(provider, { apiKey: '', isSaving: false, message: '已保存' })
    } catch (error) {
      updateApiForm(provider, {
        isSaving: false,
        message: getApiErrorMessage(error, '保存失败'),
      })
    }
  }

  async function handleVerifyApiKey(provider: ApiKeyProvider) {
    updateApiForm(provider, { isSaving: true, message: null })
    try {
      const verified = await UserService.verifyApiKey(provider)
      setApiKeys((records) => [verified, ...records.filter((item) => item.provider !== provider)])
      updateApiForm(provider, { isSaving: false, message: '验证通过' })
    } catch (error) {
      updateApiForm(provider, {
        isSaving: false,
        message: getApiErrorMessage(error, '验证失败'),
      })
    }
  }

  async function handleDeleteApiKey(provider: ApiKeyProvider) {
    updateApiForm(provider, { isSaving: true, message: null })
    try {
      await UserService.deleteApiKey(provider)
      setApiKeys((records) => records.filter((item) => item.provider !== provider))
      updateApiForm(provider, {
        apiKey: '',
        baseUrl: '',
        region: '',
        isSaving: false,
        message: '已删除',
      })
    } catch (error) {
      updateApiForm(provider, {
        isSaving: false,
        message: getApiErrorMessage(error, '删除失败'),
      })
    }
  }

  if (!user) {
    return null
  }

  const used = quota?.used ?? user.monthly_used
  const total = quota?.total ?? user.monthly_quota
  const remaining = quota?.remaining ?? Math.max(total - used, 0)
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0
  const isWarning = pct >= 80
  const displayName = user.nickname || user.phone || 'PodFlow User'
  const avatarLetter = displayName.charAt(0).toUpperCase()
  const joinedDate = new Date(user.created_at).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <main className="profile-page">
      <h1 className="profile-title">个人中心</h1>

      <div className="profile-card">
        <p className="profile-card__title">账号信息</p>
        <div className="profile-identity">
          <div className="profile-avatar" aria-hidden="true">
            {avatarLetter}
          </div>
          <div className="profile-identity__info">
            <div className="profile-nickname-wrapper">
              <span className="profile-nickname">{displayName}</span>
            </div>
            {user.phone && (
              <p className="profile-phone">
                手机号 {user.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')}
              </p>
            )}
            <p className="profile-joined">注册时间 {joinedDate}</p>
          </div>
        </div>
      </div>

      <div className="profile-card">
        <p className="profile-card__title">本月额度</p>
        <div className="profile-quota-row">
          <span className="profile-quota-label">剩余可用次数</span>
          <span className="profile-quota-value">
            {remaining} <span>/ {total} 次</span>
          </span>
        </div>
        <ProgressBar value={pct} variant={isWarning ? 'warning' : 'accent'} />
        {quota?.reset_at && (
          <p className="profile-quota-reset">
            下次重置 {new Date(quota.reset_at).toLocaleDateString('zh-CN')}
          </p>
        )}
      </div>

      <div className="profile-card">
        <p className="profile-card__title">任务与 API 配置</p>

        <div className="profile-setting-row">
          <div className="profile-setting-info">
            <p className="profile-setting-label">任务完成提醒</p>
            <p className="profile-setting-desc">任务完成后在页面内显示提示。</p>
          </div>
          <Toggle
            id="pref-notify-toggle"
            checked={notifyOnComplete}
            onChange={handleNotifyToggle}
          />
        </div>

        <div className="profile-setting-row">
          <div className="profile-setting-info">
            <p className="profile-setting-label">默认输出格式</p>
            <p className="profile-setting-desc">用于新建任务时的默认音频格式。</p>
          </div>
          <select
            className="profile-setting-select"
            value={defaultFormat}
            onChange={(event) => handleFormatChange(event.target.value as OutputFormatPreference)}
            id="pref-format-select"
            aria-label="默认输出格式"
          >
            <option value="mp3">MP3</option>
            <option value="wav">WAV</option>
            <option value="aac">AAC</option>
          </select>
        </div>

        <div className="profile-setting-row">
          <div className="profile-setting-info">
            <p className="profile-setting-label">语言翻译模型</p>
            <p className="profile-setting-desc">新建任务和继续生成时使用的翻译服务。</p>
          </div>
          <select
            className="profile-setting-select"
            value={translationProvider}
            onChange={(event) => handleTranslationProviderChange(event.target.value as TranslationProviderPreference)}
            id="pref-translation-provider-select"
            aria-label="语言翻译模型"
          >
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
          </select>
        </div>

        <div className="profile-setting-row">
          <div className="profile-setting-info">
            <p className="profile-setting-label">声纹克隆模式</p>
            <p className="profile-setting-desc">新建任务默认使用的声纹处理策略。</p>
          </div>
          <select
            className="profile-setting-select"
            value={voiceCloneMode}
            onChange={(event) => handleVoiceCloneModeChange(event.target.value as VoiceCloneModePreference)}
            id="pref-voice-clone-mode-select"
            aria-label="声纹克隆模式"
          >
            <option value="best_effort">商业声纹优先</option>
            <option value="required">必须克隆成功</option>
            <option value="off">关闭声纹克隆</option>
          </select>
        </div>

        <div className="profile-setting-row">
          <div className="profile-setting-info">
            <p className="profile-setting-label">声纹克隆引擎</p>
            <p className="profile-setting-desc">新建任务使用的声纹克隆服务。VoxCPM 为自托管开源模型，需在 worker 上配置 GPU。</p>
          </div>
          <select
            className="profile-setting-select"
            value={voiceCloneProvider}
            onChange={(event) => handleVoiceCloneProviderChange(event.target.value as VoiceCloneProviderPreference)}
            id="pref-voice-clone-provider-select"
            aria-label="声纹克隆引擎"
          >
            <option value="elevenlabs">ElevenLabs（商业 API）</option>
            <option value="voxcpm">VoxCPM（自托管，内测对比）</option>
          </select>
        </div>

        <div className="profile-setting-row">
          <div className="profile-setting-info">
            <p className="profile-setting-label">声纹授权确认</p>
            <p className="profile-setting-desc">确认你有权处理上传音频中的声音。</p>
          </div>
          <Toggle
            id="pref-voice-clone-consent-toggle"
            checked={voiceCloneConsentConfirmed}
            onChange={handleVoiceCloneConsentChange}
          />
        </div>
      </div>

      <div className="profile-card">
        <p className="profile-card__title">API 管理</p>
        <div className="profile-api-list">
          {API_PROVIDERS.map((provider) => {
            const record = findApiKey(provider.key)
            const form = apiForms[provider.key]
            return (
              <div className="profile-api-row" key={provider.key}>
                <div className="profile-api-row__header">
                  <div className="profile-api-row__name">
                    <KeyRound className="profile-api-row__icon" />
                    <span>{provider.label}</span>
                  </div>
                  {record?.verified_at && (
                    <span className="profile-api-row__verified">
                      <CheckCircle className="profile-api-row__verified-icon" />
                      已验证
                    </span>
                  )}
                </div>
                <div className="profile-api-row__meta">
                  {record ? `当前密钥 ${record.masked_key}` : '尚未配置'}
                  {record?.last_error ? ` · ${record.last_error}` : ''}
                  {provider.description ? ` · ${provider.description}` : ''}
                </div>
                {(provider.helpSteps?.length || provider.helpUrl) && (
                  <details className="profile-api-row__help">
                    <summary className="profile-api-row__help-summary">
                      如何获取 {provider.label} 密钥？
                    </summary>
                    {provider.helpSteps?.length ? (
                      <ol className="profile-api-row__help-steps">
                        {provider.helpSteps.map((step, index) => (
                          <li key={index}>{step}</li>
                        ))}
                      </ol>
                    ) : null}
                    {provider.helpUrl && (
                      <a
                        className="profile-api-row__help-link"
                        href={provider.helpUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        前往获取页面 ↗
                      </a>
                    )}
                  </details>
                )}
                <div className="profile-api-row__grid">
                  <input
                    className="profile-api-input"
                    type="password"
                    value={form.apiKey}
                    placeholder={record ? '留空则不修改密钥' : provider.placeholder}
                    onChange={(event) => updateApiForm(provider.key, { apiKey: event.target.value })}
                  />
                  {provider.supportsBaseUrl !== false && (
                    <input
                      className="profile-api-input"
                      value={form.baseUrl}
                      placeholder="接口地址（可选）"
                      onChange={(event) => updateApiForm(provider.key, { baseUrl: event.target.value })}
                    />
                  )}
                  {provider.supportsRegion !== false && (
                    <input
                      className="profile-api-input"
                      value={form.region}
                      placeholder="区域（可选）"
                      onChange={(event) => updateApiForm(provider.key, { region: event.target.value })}
                    />
                  )}
                </div>
                <div className="profile-api-row__actions">
                  <button
                    className="profile-api-btn profile-api-btn--primary"
                    disabled={form.isSaving}
                    onClick={() => handleSaveApiKey(provider.key)}
                  >
                    保存
                  </button>
                  <button
                    className="profile-api-btn"
                    disabled={form.isSaving || !record}
                    onClick={() => handleVerifyApiKey(provider.key)}
                  >
                    验证
                  </button>
                  <button
                    className="profile-api-btn profile-api-btn--danger"
                    disabled={form.isSaving || !record}
                    onClick={() => handleDeleteApiKey(provider.key)}
                    aria-label={`删除 ${provider.label} 密钥`}
                  >
                    <Trash2 className="profile-api-btn__icon" />
                  </button>
                  {form.message && <span className="profile-api-row__message">{form.message}</span>}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="profile-card profile-logout-card">
        <p className="profile-card__title">账号操作</p>
        <button
          className="profile-logout-btn"
          onClick={() => setShowConfirm(true)}
          id="profile-logout-btn"
        >
          退出登录
        </button>
      </div>

      {showConfirm && (
        <div className="confirm-overlay" onClick={() => setShowConfirm(false)}>
          <div className="confirm-dialog" onClick={(event) => event.stopPropagation()}>
            <p className="confirm-dialog__title">确认退出？</p>
            <p className="confirm-dialog__desc">
              退出后需要重新登录，但后台任务会继续处理，不会中断。
            </p>
            <div className="confirm-dialog__actions">
              <button
                className="confirm-dialog__cancel"
                onClick={() => setShowConfirm(false)}
                id="confirm-logout-cancel"
              >
                取消
              </button>
              <button
                className="confirm-dialog__confirm"
                onClick={handleLogout}
                id="confirm-logout-ok"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
