from typing import Literal, Optional

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PCT_APP_ENV: Literal["dev", "demo", "prod"] = "dev"
    PCT_APP_MODE: Literal["demo", "prod"] = "prod"
    PCT_AUTH_MODE: Literal["demo", "sms"] = "sms"
    PCT_ENABLE_SMS_LOGIN: bool = True
    PCT_SHOW_DEMO_BANNER: bool = False
    PCT_ENABLE_SAMPLE_TASKS: bool = False
    PCT_ALLOW_USER_UPLOAD: bool = True
    PCT_ENABLE_REAL_COST_FEATURES: bool = True
    PCT_DEMO_USER_PHONE: str = "13800138000"
    PCT_DEMO_USER_NICKNAME: str = "PodFlow Demo"

    PCT_SECRET_KEY: SecretStr

    PCT_DATABASE_URL: PostgresDsn
    PCT_DATABASE_POOL_SIZE: int = 10
    PCT_AUTO_MIGRATE_ON_STARTUP: bool = True

    PCT_REDIS_URL: RedisDsn

    PCT_S3_ENDPOINT: str
    PCT_S3_PUBLIC_ENDPOINT: Optional[str] = None
    PCT_S3_BUCKET: str = "podcast-translator-audio"
    PCT_S3_ACCESS_KEY: Optional[SecretStr] = None
    PCT_S3_SECRET_KEY: Optional[SecretStr] = None

    PCT_HF_TOKEN: Optional[SecretStr] = None
    PCT_DASHSCOPE_API_KEY: Optional[SecretStr] = None
    PCT_DASHSCOPE_BASE_HTTP_URL: Optional[str] = None
    PCT_DASHSCOPE_BASE_WEBSOCKET_URL: Optional[str] = None
    PCT_ASR_PROVIDER: Literal["whisper", "sensevoice"] = "whisper"
    PCT_ASR_MODEL: str = "medium"
    PCT_ASR_DEVICE: str = "auto"
    PCT_ASR_COMPUTE_TYPE: str = "default"
    PCT_ASR_BEAM_SIZE: int = 5
    PCT_TTS_PROVIDER: Literal["cosyvoice", "fish_speech"] = "cosyvoice"
    PCT_VOICE_CLONE_PROVIDER: Literal["elevenlabs", "cosyvoice", "voxcpm"] = "elevenlabs"
    PCT_COSYVOICE_MODEL: str = "cosyvoice-v2"
    PCT_COSYVOICE_FALLBACK_VOICE: str = "longxiaochun_v2"
    PCT_COSYVOICE_FALLBACK_VOICE_MALE: str = "longxiaocheng_v2"
    PCT_COSYVOICE_FALLBACK_VOICE_FEMALE: str = "longxiaochun_v2"
    PCT_COSYVOICE_ENABLE_ENROLLMENT: bool = True
    PCT_COSYVOICE_ENROLLMENT_PREFIX: str = "podflow"
    PCT_COSYVOICE_MODEL_BALANCED: str = "cosyvoice-v3-flash"
    PCT_COSYVOICE_MODEL_ECONOMY: str = "cosyvoice-v3.5-flash"
    PCT_DASHSCOPE_TTS_TIMEOUT_MILLIS: int = 30000
    PCT_DASHSCOPE_TTS_MAX_RETRIES: int = 10
    PCT_DASHSCOPE_TTS_RETRY_BACKOFF_SECONDS: float = 4.0
    PCT_DASHSCOPE_TTS_SEGMENT_DELAY_SECONDS: float = 1.0
    PCT_DASHSCOPE_TTS_RPS: float = 2.0
    PCT_ELEVENLABS_API_KEY: Optional[SecretStr] = None
    PCT_ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io"
    PCT_ELEVENLABS_TTS_MODEL: str = "eleven_multilingual_v2"
    PCT_ELEVENLABS_OUTPUT_FORMAT: str = "mp3_44100_128"
    PCT_ELEVENLABS_TIMEOUT_SECONDS: int = 60
    PCT_ELEVENLABS_MAX_RETRIES: int = 3
    PCT_ELEVENLABS_RETRY_BACKOFF_SECONDS: float = 2.0
    PCT_ELEVENLABS_REMOVE_BACKGROUND_NOISE: bool = True
    # VoxCPM: self-hosted, zero-shot voice clone (no API key). Requires `pip install voxcpm soundfile`
    # and a GPU (~8GB VRAM) for usable speed. Added as an acceptance-comparison provider alongside ElevenLabs.
    PCT_VOXCPM_MODEL: str = "openbmb/VoxCPM-0.5B"
    PCT_VOXCPM_DEVICE: str = "auto"
    PCT_VOXCPM_CFG_VALUE: float = 2.0
    PCT_VOXCPM_INFERENCE_TIMESTEPS: int = 10
    PCT_VOXCPM_DENOISE: bool = True
    PCT_VOXCPM_NORMALIZE: bool = True
    PCT_VOXCPM_RETRY_BADCASE: bool = True
    PCT_VOXCPM_RETRY_BADCASE_MAX_TIMES: int = 3
    PCT_VOICE_CLONE_RETENTION_DAYS: int = 7
    PCT_REQUIRE_VOICE_CLONE_CONSENT: bool = False
    PCT_TTS_CONCURRENCY: int = 4
    PCT_TTS_MERGE_SHORT_SEGMENTS: bool = True
    PCT_TTS_MERGE_MAX_SECONDS: float = 15.0
    PCT_TTS_MERGE_MAX_GAP_SECONDS: float = 0.8
    PCT_TRANSLATION_PROVIDER: Literal["openai", "deepseek"] = "openai"
    PCT_OPENAI_API_KEY: Optional[SecretStr] = None
    PCT_OPENAI_BASE_URL: Optional[str] = None
    PCT_DEEPSEEK_API_KEY: Optional[SecretStr] = None
    PCT_DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    PCT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    PCT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    PCT_SMS_PROVIDER: Literal["mock", "aliyun", "tencent"] = "mock"
    PCT_SMS_ACCESS_KEY_ID: Optional[str] = None
    PCT_SMS_ACCESS_KEY_SECRET: Optional[SecretStr] = None
    PCT_SMS_SIGN_NAME: Optional[str] = None
    PCT_SMS_TEMPLATE_CODE: Optional[str] = None
    PCT_SMS_ENDPOINT: str = "dysmsapi.aliyuncs.com"
    # Fixed code used only when PCT_SMS_PROVIDER == "mock" (local/CI). Real providers
    # generate a random code stored in Redis instead.
    PCT_MOCK_SMS_CODE: str = "123456"
    PCT_SMS_CODE_TTL_SECONDS: int = 300
    PCT_SMS_CODE_COOLDOWN_SECONDS: int = 60
    PCT_SMS_MAX_VERIFY_ATTEMPTS: int = 5

    # WeChat OAuth is still a mock placeholder; keep it disabled until real OAuth lands
    # so mock openids can never be issued in production.
    PCT_ENABLE_WECHAT_LOGIN: bool = False
    PCT_WECHAT_APP_ID: Optional[str] = None
    PCT_WECHAT_APP_SECRET: Optional[SecretStr] = None

    PCT_DEFAULT_MONTHLY_QUOTA: int = 5
    # Production admission controls. 0 = unlimited (default, preserves current behavior).
    PCT_MAX_ACTIVE_TASKS_PER_USER: int = 0
    # Comma-separated phone allowlist for SMS login; empty = allow all. Ignored in mock SMS.
    PCT_SMS_PHONE_ALLOWLIST: str = ""
    PCT_CREDENTIALS_ENCRYPTION_KEY: Optional[SecretStr] = None
    PCT_INTERMEDIATE_ARTIFACT_RETENTION_DAYS: int = 7
    PCT_PIPELINE_MODE: Literal["real", "mock"] = "real"
    PCT_MOCK_PIPELINE_STAGE_DELAY_SECONDS: float = 0.2
    PCT_PIPELINE_TASK_TIME_LIMIT_SECONDS: int = 172800
    PCT_PIPELINE_TASK_SOFT_TIME_LIMIT_SECONDS: int = 169200
    # Demucs source separation. htdemucs (single model) uses ~4x less memory than the
    # htdemucs_ft bag; --segment bounds peak memory regardless of audio length. Tuned to
    # avoid OOM on CPU workers. Set PCT_DEMUCS_MODEL=htdemucs_ft to trade memory for quality.
    PCT_DEMUCS_MODEL: str = "htdemucs"
    PCT_DEMUCS_SEGMENT_SECONDS: int = 7
    PCT_DEMUCS_JOBS: int = 1
    PCT_DEMUCS_DEVICE: Optional[str] = None  # None = autodetect; e.g. "cpu" / "cuda"
    PCT_ENABLE_LONG_AUDIO_PIPELINE: bool = True
    PCT_LONG_AUDIO_THRESHOLD_SECONDS: int = 1800
    PCT_MAX_AUDIO_DURATION_SECONDS: int = 18000
    PCT_MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024 * 1024
    PCT_AUDIO_CHUNK_SECONDS: int = 600
    PCT_AUDIO_CHUNK_OVERLAP_SECONDS: int = 5
    PCT_TRANSLATION_BATCH_SIZE: int = 20
    PCT_TTS_BATCH_SIZE: int = 20
    PCT_PROVIDER_PREFLIGHT_TIMEOUT_SECONDS: int = 10
    PCT_PROVIDER_PREFLIGHT_CACHE_SECONDS: int = 600
    # Transient network blips (e.g. flaky TLS to huggingface.co) should retry rather than
    # pause the whole task. Definitive HTTP errors (401/403/quota) are never retried.
    PCT_PREFLIGHT_RETRY_ATTEMPTS: int = 3
    PCT_PREFLIGHT_RETRY_BACKOFF_SECONDS: float = 1.5
    PCT_CLEANUP_INTERMEDIATES_ON_COMPLETION: bool = True
    # Celery beat cadence for the ElevenLabs voice retention sweep; <= 0 disables it.
    PCT_VOICE_CLONE_CLEANUP_INTERVAL_HOURS: int = 24
    PCT_CHUNK_PIPELINE_MAX_IN_FLIGHT: int = 3
    PCT_CHUNK_PIPELINE_STAGE_WORKERS: int = 1
    # Overlap the network-bound S4 translation with the compute-bound front-half (S1-S3) in the
    # long-audio pipeline: each chunk's transcript is translated as soon as it is transcribed,
    # on a background worker, instead of running one serial translation pass over the whole
    # transcript after the front-half finishes. Translations flow into the aggregated segments,
    # so the post-front-half translation stage becomes a fast no-op. Set False to restore the
    # strictly-sequential behaviour.
    PCT_OVERLAP_TRANSLATION_WITH_FRONT_HALF: bool = True

    # --- Worker liveness / stall detection ---
    PCT_ENABLE_STALL_RECONCILER: bool = False
    # The per-task worker lock auto-expires after this TTL; an independent helper renews it
    # while the pipeline runs. Keep it short so an OOM/SIGKILL releases the lock quickly
    # (the old behaviour pinned it to the multi-day task time limit and wedged retries).
    PCT_WORKER_LOCK_TTL_SECONDS: int = 300
    # Cadence at which the worker renews the lock and writes a liveness heartbeat.
    PCT_WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 30
    # If heartbeat, ownership, and business activity are all stale for this long, Celery Beat
    # starts the two-phase reconciliation flow.
    PCT_TASK_STALL_TIMEOUT_SECONDS: int = 900
    # A missing heartbeat/lock must remain missing for this second confirmation window.
    PCT_TASK_STALL_CONFIRMATION_SECONDS: int = 300
    PCT_TASK_STALL_SCAN_INTERVAL_SECONDS: int = 60
    PCT_TASK_STALL_SCAN_BATCH_SIZE: int = 100
    # How many times a stalled task is auto-resumed before it is marked failed (avoids OOM loops).
    PCT_MAX_AUTO_RESUMES: int = 1
    # ETA calibration. Stage duration factors are tuned for GPU; multiply them for CPU-only
    # boxes. The live estimator also self-adapts using this task's measured stage durations.
    PCT_ETA_DURATION_MULTIPLIER: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
