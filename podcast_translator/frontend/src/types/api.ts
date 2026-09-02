export interface SendSMSRequest {
  phone: string
}

export interface SMSLoginRequest {
  phone: string
  code: string
}

export interface WechatLoginRequest {
  code: string
}

export interface RefreshRequest {
  refresh_token: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  exp: string
}

export interface UserResponse {
  id: string
  phone: string | null
  nickname: string | null
  avatar_url: string | null
  monthly_quota: number
  monthly_used: number
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface QuotaResponse {
  total: number
  used: number
  remaining: number
  reset_at: string | null
}

export type ApiKeyProvider = 'dashscope' | 'openai' | 'deepseek' | 'huggingface' | 'elevenlabs'

export interface UserApiKeyResponse {
  provider: ApiKeyProvider
  masked_key: string
  base_url: string | null
  region: string | null
  enabled: boolean
  verified_at: string | null
  last_error: string | null
  updated_at: string
}

export interface UserApiKeyUpdateRequest {
  api_key?: string
  base_url?: string | null
  region?: string | null
  enabled?: boolean
}

export type TaskStatus = 'pending' | 'processing' | 'paused' | 'completed' | 'failed'

export type PipelineStage =
  | 'uploaded'
  | 'preparing'
  | 'source_separation'
  | 'speaker_diarization'
  | 'asr_transcription'
  | 'translation'
  | 'voice_clone_tts'
  | 'temporal_alignment'
  | 'final_mixing'

export interface TaskConfig {
  target_language?: string
  speaker_count?: number
  output_format?: string
  translation_provider?: 'deepseek' | 'openai'
  voice_clone_provider?: 'elevenlabs' | 'cosyvoice' | 'voxcpm'
  tts_model_tier?: 'quality' | 'balanced' | 'economy'
  voice_clone_mode?: 'off' | 'best_effort' | 'required'
  voice_clone_consent_confirmed?: boolean
  [key: string]: unknown
}

export interface TaskStageRunResponse {
  stage: string
  attempt: number
  status: string
  started_at: string
  finished_at: string | null
  items_total: number | null
  items_done: number | null
  cost_estimate: number | null
  error_code: string | null
  metrics: Record<string, unknown> | null
}

export interface TaskSpeakerResponse {
  label: string
  gender: string | null
  pitch_hz: number | null
  voice_provider: string | null
  voice_id: string | null
  voice_model: string | null
  enrollment_status: string | null
  fallback_reason: string | null
}

export interface TaskSegmentResponse {
  index: number
  speaker_label: string | null
  start_time: number
  end_time: number
  original_text: string | null
  translated_text: string | null
}

export interface TaskResponse {
  id: string
  user_id: string
  status: TaskStatus
  current_stage: PipelineStage | string | null
  progress_percent: number
  stage_progress_percent?: number | null
  source_file_name: string | null
  source_audio_url: string | null
  output_audio_url: string | null
  audio_duration: number | null
  eta_seconds?: number | null
  config: TaskConfig | null
  error_message: string | null
  paused_at: string | null
  pause_reason_code: string | null
  provider_error_code: string | null
  created_at: string
  finished_at: string | null
  stage_runs?: TaskStageRunResponse[]
  speakers?: TaskSpeakerResponse[]
}

export interface WSProgressMessage {
  task_id: string
  stage: PipelineStage | string | null
  progress_percent: number
  status: TaskStatus
  error_message?: string | null
  pause_reason_code?: string | null
  provider_error_code?: string | null
  output_audio_url?: string | null
  audio_duration?: number | null
  processed_seconds?: number | null
  total_seconds?: number | null
  chunk_index?: number | null
  chunk_count?: number | null
  stage_progress_percent?: number | null
  eta_seconds?: number | null
  finished_at?: string | null
  event?: string | null
}

export interface APIError {
  detail: string
  status_code?: number
}

export interface PaginationParams {
  skip: number
  limit: number
}
