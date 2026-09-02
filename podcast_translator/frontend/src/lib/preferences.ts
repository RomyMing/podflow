export type OutputFormatPreference = 'mp3' | 'wav' | 'aac'
export type TranslationProviderPreference = 'deepseek' | 'openai'
export type VoiceCloneModePreference = 'off' | 'best_effort' | 'required'
export type VoiceCloneProviderPreference = 'elevenlabs' | 'voxcpm'

export const LS_NOTIFY_KEY = 'podflow:notify_on_complete'
export const LS_FORMAT_KEY = 'podflow:default_format'
export const LS_TRANSLATION_PROVIDER_KEY = 'podflow:translation_provider'
export const LS_VOICE_CLONE_MODE_KEY = 'podflow:voice_clone_mode'
export const LS_VOICE_CLONE_PROVIDER_KEY = 'podflow:voice_clone_provider'
export const LS_VOICE_CLONE_CONSENT_KEY = 'podflow:voice_clone_consent_confirmed'

const OUTPUT_FORMATS = new Set<OutputFormatPreference>(['mp3', 'wav', 'aac'])
const TRANSLATION_PROVIDERS = new Set<TranslationProviderPreference>(['deepseek', 'openai'])
const VOICE_CLONE_MODES = new Set<VoiceCloneModePreference>(['off', 'best_effort', 'required'])
const VOICE_CLONE_PROVIDERS = new Set<VoiceCloneProviderPreference>(['elevenlabs', 'voxcpm'])

function readLocalStorage(key: string): string | null {
  if (typeof window === 'undefined') {
    return null
  }
  return window.localStorage.getItem(key)
}

function writeLocalStorage(key: string, value: string): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(key, value)
}

export function getDefaultOutputFormat(): OutputFormatPreference {
  const value = readLocalStorage(LS_FORMAT_KEY)
  return OUTPUT_FORMATS.has(value as OutputFormatPreference)
    ? (value as OutputFormatPreference)
    : 'mp3'
}

export function setDefaultOutputFormat(format: OutputFormatPreference): void {
  writeLocalStorage(LS_FORMAT_KEY, format)
}

export function getTranslationProviderPreference(): TranslationProviderPreference {
  const value = readLocalStorage(LS_TRANSLATION_PROVIDER_KEY)
  return TRANSLATION_PROVIDERS.has(value as TranslationProviderPreference)
    ? (value as TranslationProviderPreference)
    : 'deepseek'
}

export function setTranslationProviderPreference(provider: TranslationProviderPreference): void {
  writeLocalStorage(LS_TRANSLATION_PROVIDER_KEY, provider)
}

export function getVoiceCloneModePreference(): VoiceCloneModePreference {
  const value = readLocalStorage(LS_VOICE_CLONE_MODE_KEY)
  return VOICE_CLONE_MODES.has(value as VoiceCloneModePreference)
    ? (value as VoiceCloneModePreference)
    : 'best_effort'
}

export function setVoiceCloneModePreference(mode: VoiceCloneModePreference): void {
  writeLocalStorage(LS_VOICE_CLONE_MODE_KEY, mode)
}

export function getVoiceCloneProviderPreference(): VoiceCloneProviderPreference {
  const value = readLocalStorage(LS_VOICE_CLONE_PROVIDER_KEY)
  return VOICE_CLONE_PROVIDERS.has(value as VoiceCloneProviderPreference)
    ? (value as VoiceCloneProviderPreference)
    : 'elevenlabs'
}

export function setVoiceCloneProviderPreference(provider: VoiceCloneProviderPreference): void {
  writeLocalStorage(LS_VOICE_CLONE_PROVIDER_KEY, provider)
}

export function getVoiceCloneConsentPreference(): boolean {
  return readLocalStorage(LS_VOICE_CLONE_CONSENT_KEY) === 'true'
}

export function setVoiceCloneConsentPreference(confirmed: boolean): void {
  writeLocalStorage(LS_VOICE_CLONE_CONSENT_KEY, String(confirmed))
}
