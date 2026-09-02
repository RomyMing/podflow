import ipaddress
import logging
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, VoiceEnrollmentService
from pydub import AudioSegment

from src.config import settings
from src.core.provider_errors import TaskPausedError, pause_for_provider_error
from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.utils import run_sync
from src.pipeline.voice_providers import ElevenLabsVoiceProvider, VoxCpmVoiceProvider
from src.services.storage_service import StorageService
from src.services.user_api_key_service import resolve_provider_credentials_sync

logger = logging.getLogger(__name__)


SYNTH_AUDIO_EXTENSION = ".mp3"
SYNTH_AUDIO_CONTENT_TYPE = "audio/mpeg"
NON_RETRYABLE_DASHSCOPE_ERROR_CODES = {
    "Arrearage",
    "InvalidApiKey",
    "InvalidParameter",
    "Forbidden",
}
TRANSIENT_TTS_ERROR_MARKERS = (
    "websocket connection could not established",
    "UNEXPECTED_EOF_WHILE_READING",
    "EOF occurred in violation of protocol",
    "Connection reset",
    "Connection aborted",
    "timed out",
    "TimeoutError",
)


@dataclass(frozen=True)
class SynthUnit:
    segment_id: int
    segment_ids: list[int]
    speaker_id: str
    text: str
    start: float
    end: float

    @property
    def object_suffix(self) -> str:
        if len(self.segment_ids) == 1:
            return f"seg_{self.segment_id}"
        return f"seg_{self.segment_ids[0]}_{self.segment_ids[-1]}"


class TokenBucketRateLimiter:
    def __init__(self, rate_per_second: float):
        self.min_interval = 1.0 / max(rate_per_second, 0.1)
        self._lock = threading.Lock()
        self._next_available = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_available - now)
            self._next_available = max(now, self._next_available) + self.min_interval
        if wait_seconds > 0:
            time.sleep(wait_seconds)


class DashScopeTTSProviderError(RuntimeError):
    def __init__(self, message: str, response=None):
        self.response = response
        self.error_code, self.error_message = parse_dashscope_error(response)
        detail = message
        if self.error_code or self.error_message:
            detail = f"{message}: {self.error_code or 'UnknownError'} - {self.error_message or response}"
        super().__init__(detail)

    @property
    def retryable(self) -> bool:
        return self.error_code not in NON_RETRYABLE_DASHSCOPE_ERROR_CODES


def parse_dashscope_error(response) -> tuple[str | None, str | None]:
    if not isinstance(response, dict):
        return None, None
    header = response.get("header") or {}
    return header.get("error_code"), header.get("error_message")


def is_transient_tts_error(exc: Exception) -> bool:
    message = str(exc)
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        message = f"{message} {cause}"
    return any(marker in message for marker in TRANSIENT_TTS_ERROR_MARKERS)


def get_audio_duration(file_path: str) -> float:
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception as exc:
        logger.error("Error reading audio duration for %s: %s", file_path, exc)
        return 0.0


def is_cloud_reachable_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False

    hostname = parsed.hostname.lower()
    if hostname in {"localhost"} or hostname.endswith(".local"):
        return False

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return True

    return not (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved)


def speaker_fallback_voice(gender: str | None) -> str:
    if gender == "male":
        return settings.PCT_COSYVOICE_FALLBACK_VOICE_MALE
    if gender == "female":
        return settings.PCT_COSYVOICE_FALLBACK_VOICE_FEMALE
    return settings.PCT_COSYVOICE_FALLBACK_VOICE


def speaker_legacy_fallback_voice(gender: str | None) -> str:
    if gender == "male":
        return "longxiaocheng"
    if gender == "female":
        return "longxiaochun"
    return "longxiaochun"


def enrollment_prefix(task_id: str, speaker_id: str) -> str:
    raw = f"{settings.PCT_COSYVOICE_ENROLLMENT_PREFIX}{task_id[:4]}{speaker_id[-2:]}"
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw)
    return (cleaned or "podflow")[:10]


def normalize_voice_clone_provider(provider: str | None) -> str:
    cleaned = str(provider or settings.PCT_VOICE_CLONE_PROVIDER).strip().lower()
    if cleaned not in {"elevenlabs", "cosyvoice", "voxcpm"}:
        return settings.PCT_VOICE_CLONE_PROVIDER
    return cleaned


class CosyVoiceTTSStage(StageProcessor):
    def __init__(self, next_processor: "StageProcessor" = None):
        super().__init__(next_processor)
        self.storage_service = StorageService()
        self.api_key: str | None = None
        self.elevenlabs_provider: ElevenLabsVoiceProvider | None = None
        self.voxcpm_provider: VoxCpmVoiceProvider | None = None

    @property
    def stage(self) -> TaskStage:
        return TaskStage.SYNTHESIZING

    def _write_audio_payload(self, audio_payload, output_path: str) -> None:
        if isinstance(audio_payload, (bytes, bytearray)):
            with open(output_path, "wb") as out_file:
                out_file.write(audio_payload)
            return

        get_audio_data = getattr(audio_payload, "get_audio_data", None)
        if callable(get_audio_data):
            audio_data = get_audio_data()
            if audio_data is not None:
                with open(output_path, "wb") as out_file:
                    out_file.write(audio_data)
                return

        response = getattr(audio_payload, "get_response", lambda: None)()
        raise RuntimeError(f"TTS synthesis returned no audio data: {response}")

    def _synthesize_with_voice(self, text: str, output_path: str, *, model: str, voice: str) -> None:
        max_retries = max(1, settings.PCT_DASHSCOPE_TTS_MAX_RETRIES)
        last_exc: Exception | None = None
        attempts_used = 0

        for attempt in range(1, max_retries + 1):
            attempts_used = attempt
            try:
                synthesizer = SpeechSynthesizer(model=model, voice=voice)
                audio = synthesizer.call(
                    text,
                    timeout_millis=settings.PCT_DASHSCOPE_TTS_TIMEOUT_MILLIS,
                )
                if audio is None:
                    raise DashScopeTTSProviderError(
                        "TTS synthesis returned no audio data",
                        synthesizer.get_response(),
                    )
                self._write_audio_payload(audio, output_path)
                return
            except Exception as exc:
                # Permanent provider problems (billing/auth/quota) pause now; transient
                # connectivity keeps retrying and only pauses after the loop is exhausted.
                pause_error = pause_for_provider_error(
                    exc,
                    provider="dashscope",
                    stage=self.stage,
                    prefix="DashScope TTS provider is unavailable",
                    include_transient=False,
                )
                if pause_error is not None:
                    raise pause_error from exc
                last_exc = exc
                retryable = not isinstance(exc, DashScopeTTSProviderError) or exc.retryable
                if not retryable:
                    logger.error(
                        "DashScope TTS failed with non-retryable provider error for %s/%s: %s",
                        model,
                        voice,
                        exc,
                    )
                    break
                if attempt >= max_retries:
                    break

                delay = max(0.0, settings.PCT_DASHSCOPE_TTS_RETRY_BACKOFF_SECONDS) * attempt
                logger.warning(
                    "DashScope TTS attempt %s/%s failed for %s/%s: %s. Retrying in %.1fs.",
                    attempt,
                    max_retries,
                    model,
                    voice,
                    exc,
                    delay,
                )
                if delay > 0:
                    time.sleep(delay)

        pause_error = pause_for_provider_error(
            last_exc or RuntimeError("unknown TTS failure"),
            provider="dashscope",
            stage=self.stage,
            prefix=f"DashScope TTS failed after {attempts_used} attempt(s)",
        )
        if pause_error is not None:
            raise pause_error from last_exc
        raise RuntimeError(f"DashScope TTS failed after {attempts_used} attempt(s): {last_exc}") from last_exc

    def _configure_dashscope_credentials(self, ctx: PipelineContext, *, required: bool) -> bool:
        if self.api_key:
            return True
        credentials = resolve_provider_credentials_sync(ctx.user_id, "dashscope")
        if credentials is None:
            if required:
                raise TaskPausedError(
                    "DashScope API key is not configured. Add it in Profile > API management.",
                    provider="dashscope",
                    reason_code="provider_credentials_missing",
                    stage=self.stage,
                )
            return False
        self.api_key = credentials.api_key
        dashscope.api_key = credentials.api_key
        if credentials.base_url:
            dashscope.base_http_api_url = credentials.base_url.rstrip("/")
            if "dashscope-intl" in credentials.base_url:
                dashscope.base_websocket_api_url = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"
            elif "dashscope-us" in credentials.base_url:
                dashscope.base_websocket_api_url = "wss://dashscope-us.aliyuncs.com/api-ws/v1/inference"
        elif settings.PCT_DASHSCOPE_BASE_HTTP_URL:
            dashscope.base_http_api_url = settings.PCT_DASHSCOPE_BASE_HTTP_URL.rstrip("/")
        if settings.PCT_DASHSCOPE_BASE_WEBSOCKET_URL:
            dashscope.base_websocket_api_url = settings.PCT_DASHSCOPE_BASE_WEBSOCKET_URL.rstrip("/")
        return True

    def _configure_credentials(self, ctx: PipelineContext) -> None:
        config = getattr(ctx, "config", None) or {}
        voice_clone_mode = config.get("voice_clone_mode") or "best_effort"
        voice_clone_provider = normalize_voice_clone_provider(config.get("voice_clone_provider"))

        if voice_clone_provider == "voxcpm" and voice_clone_mode != "off":
            # Self-hosted, no credentials required. The model is loaded lazily on first synth.
            self.voxcpm_provider = VoxCpmVoiceProvider()
            return

        if voice_clone_provider == "elevenlabs" and voice_clone_mode != "off":
            credentials = resolve_provider_credentials_sync(ctx.user_id, "elevenlabs")
            if credentials is None:
                raise TaskPausedError(
                    "ElevenLabs API key is not configured. Add it in Profile > API management.",
                    provider="elevenlabs",
                    reason_code="provider_credentials_missing",
                    stage=self.stage,
                )
            self.elevenlabs_provider = ElevenLabsVoiceProvider(credentials)
            return

        self._configure_dashscope_credentials(ctx, required=True)

    def _required_provider_pause(self, exc: Exception, *, provider: str, prefix: str) -> TaskPausedError:
        provider_error_code = getattr(exc, "error_code", None)
        status_code = getattr(exc, "status_code", None)
        if provider_error_code is None and status_code:
            provider_error_code = f"HTTP{status_code}"
        return TaskPausedError(
            f"{prefix}: {exc}",
            provider=provider,
            reason_code="provider_unavailable",
            provider_error_code=str(provider_error_code) if provider_error_code else None,
            stage=self.stage,
        )

    def _checkpoint_pipeline_state(self, ctx: PipelineContext) -> None:
        hooks = self._get_lifecycle_hooks(ctx)
        if hooks and hasattr(hooks, "on_pipeline_state_checkpoint"):
            hooks.on_pipeline_state_checkpoint(ctx)

    def _voice_model_for_tier(self, tier: str | None) -> str:
        if tier == "economy":
            return settings.PCT_COSYVOICE_MODEL_ECONOMY
        if tier == "balanced":
            return settings.PCT_COSYVOICE_MODEL_BALANCED
        return settings.PCT_COSYVOICE_MODEL

    def _synthesize_chunk(self, ctx: PipelineContext, text: str, output_path: str, speaker_profile: dict | None) -> dict:
        speaker_profile = speaker_profile or {}
        voice_id = speaker_profile.get("voice_id")
        voice_provider = speaker_profile.get("voice_provider")
        voice_clone_mode = speaker_profile.get("voice_clone_mode") or "best_effort"
        gender = speaker_profile.get("gender")
        fallback_voice = speaker_profile.get("fallback_voice") or speaker_fallback_voice(gender)
        model = speaker_profile.get("voice_model") or speaker_profile.get("model") or settings.PCT_COSYVOICE_MODEL
        prompt_wav = speaker_profile.get("prompt_wav_path")

        if voice_provider == "voxcpm" and prompt_wav and self.voxcpm_provider is not None:
            logger.info("Using VoxCPM zero-shot clone (ref=%s) for speaker %s.", prompt_wav, speaker_profile.get("id"))
            try:
                self.voxcpm_provider.synthesize_to_file(
                    text=text,
                    prompt_wav_path=prompt_wav,
                    output_path=output_path,
                    prompt_text=speaker_profile.get("prompt_text"),
                )
                return {
                    "mode": "voxcpm_cloned",
                    "provider": "voxcpm",
                    "voice": f"voxcpm:{speaker_profile.get('id')}",
                    "model": model or settings.PCT_VOXCPM_MODEL,
                }
            except TaskPausedError:
                raise
            except Exception as exc:
                if voice_clone_mode == "required":
                    raise self._required_provider_pause(
                        exc,
                        provider="voxcpm",
                        prefix="VoxCPM TTS failed in required voice clone mode",
                    ) from exc
                logger.warning(
                    "VoxCPM TTS failed for speaker %s; falling back to CosyVoice preset.",
                    speaker_profile.get("id"),
                    exc_info=True,
                )
        elif voice_provider == "elevenlabs" and voice_id and self.elevenlabs_provider is not None:
            logger.info("Using ElevenLabs cloned voice %s for speaker %s.", voice_id, speaker_profile.get("id"))
            try:
                self.elevenlabs_provider.synthesize_to_file(
                    text=text,
                    voice_id=voice_id,
                    output_path=output_path,
                    model_id=model or settings.PCT_ELEVENLABS_TTS_MODEL,
                    output_format=settings.PCT_ELEVENLABS_OUTPUT_FORMAT,
                )
                return {
                    "mode": "elevenlabs_cloned",
                    "provider": "elevenlabs",
                    "voice": voice_id,
                    "model": model or settings.PCT_ELEVENLABS_TTS_MODEL,
                }
            except Exception as exc:
                pause_error = pause_for_provider_error(
                    exc,
                    provider="elevenlabs",
                    stage=self.stage,
                    prefix="ElevenLabs TTS provider is unavailable",
                )
                if voice_clone_mode == "required":
                    if pause_error is not None:
                        raise pause_error from exc
                    raise self._required_provider_pause(
                        exc,
                        provider="elevenlabs",
                        prefix="ElevenLabs TTS failed in required voice clone mode",
                    ) from exc
                logger.warning(
                    "ElevenLabs TTS failed for speaker %s; falling back to CosyVoice preset.",
                    speaker_profile.get("id"),
                    exc_info=True,
                )
        elif voice_id:
            if not self._configure_dashscope_credentials(ctx, required=True):
                raise RuntimeError("DashScope API key is not configured. Cannot perform TTS.")
            logger.info("Using enrolled CosyVoice voice %s for speaker %s.", voice_id, speaker_profile.get("id"))
            self._synthesize_with_voice(text, output_path, model=model, voice=voice_id)
            return {"mode": "enrolled", "provider": "cosyvoice", "voice": voice_id, "model": model}

        if not self._configure_dashscope_credentials(ctx, required=True):
            raise RuntimeError("DashScope API key is not configured. Cannot perform TTS fallback.")

        fallback_model = settings.PCT_COSYVOICE_MODEL
        logger.info(
            "Using CosyVoice fallback voice %s for speaker %s (gender=%s).",
            fallback_voice,
            speaker_profile.get("id"),
            gender or "unknown",
        )
        try:
            self._synthesize_with_voice(text, output_path, model=fallback_model, voice=fallback_voice)
            return {"mode": "fallback", "provider": "cosyvoice", "voice": fallback_voice, "model": fallback_model}
        except Exception as exc:
            if isinstance(exc, TaskPausedError):
                raise
            if isinstance(exc, RuntimeError) and "Arrearage" in str(exc):
                raise
            if is_transient_tts_error(exc):
                raise
            legacy_voice = speaker_legacy_fallback_voice(gender)
            if fallback_model == "cosyvoice-v1" and fallback_voice == legacy_voice:
                raise
            logger.warning(
                "Configured CosyVoice fallback %s/%s failed. Retrying legacy %s.",
                fallback_model,
                fallback_voice,
                legacy_voice,
                exc_info=True,
            )
            self._synthesize_with_voice(text, output_path, model="cosyvoice-v1", voice=legacy_voice)
            return {"mode": "legacy_fallback", "provider": "cosyvoice", "voice": legacy_voice, "model": "cosyvoice-v1"}

    def _build_speaker_profiles(
        self,
        ctx: PipelineContext,
        temp_dir_path: Path,
        active_speaker_ids: set[str] | None = None,
    ) -> dict[str, dict]:
        profiles: dict[str, dict] = {}
        if not ctx.speakers:
            return profiles

        config = getattr(ctx, "config", None) or {}
        voice_clone_mode = config.get("voice_clone_mode") if isinstance(config, dict) else None
        if voice_clone_mode is None:
            voice_clone_mode = "best_effort"
        voice_clone_provider = normalize_voice_clone_provider(
            config.get("voice_clone_provider") if isinstance(config, dict) else None
        )
        tts_model_tier = config.get("tts_model_tier") if isinstance(config, dict) else None
        target_voice_model = self._voice_model_for_tier(tts_model_tier)
        enrollment_service = (
            VoiceEnrollmentService(api_key=self.api_key)
            if voice_clone_provider == "cosyvoice" and self.api_key
            else None
        )
        for speaker in ctx.speakers:
            speaker_id = str(speaker.get("id") or speaker.get("label") or "UNKNOWN")
            profile = {
                "id": speaker_id,
                "gender": speaker.get("gender"),
                "pitch_hz": speaker.get("pitch_hz"),
                "fallback_voice": speaker_fallback_voice(speaker.get("gender")),
                "model": settings.PCT_COSYVOICE_MODEL,
                "voice_model": speaker.get("voice_model"),
                "voice_provider": speaker.get("voice_provider"),
                "voice_id": speaker.get("voice_id"),
                "enrollment_status": speaker.get("enrollment_status"),
                "fallback_reason": speaker.get("fallback_reason"),
                "voice_clone_mode": voice_clone_mode,
            }

            if active_speaker_ids is not None and speaker_id not in active_speaker_ids:
                profiles[speaker_id] = profile
                continue

            ref_url = speaker.get("ref_audio_url")
            if ref_url:
                local_ref_path = temp_dir_path / f"ref_{speaker_id}.wav"
                logger.info("Task %s: Downloading reference audio for speaker %s.", ctx.task_id, speaker_id)
                try:
                    run_sync(self.storage_service.download_file(ref_url, str(local_ref_path)))
                    if not profile["gender"]:
                        try:
                            import torchaudio

                            from src.pipeline.voice_analysis import estimate_speaker_gender

                            waveform, sample_rate = torchaudio.load(str(local_ref_path))
                            gender, pitch_hz = estimate_speaker_gender(waveform, sample_rate)
                            profile["gender"] = gender
                            profile["pitch_hz"] = pitch_hz
                            profile["fallback_voice"] = speaker_fallback_voice(gender)
                            speaker["gender"] = gender
                            speaker["pitch_hz"] = pitch_hz
                            logger.info(
                                "Task %s: estimated speaker %s gender=%s pitch=%s from reference audio.",
                                ctx.task_id,
                                speaker_id,
                                gender,
                                pitch_hz,
                            )
                        except Exception:
                            logger.warning(
                                "Task %s: failed to estimate gender for speaker %s.",
                                ctx.task_id,
                                speaker_id,
                                exc_info=True,
                            )
                except Exception:
                    logger.warning("Task %s: Failed to download reference audio for %s.", ctx.task_id, speaker_id, exc_info=True)

                if voice_clone_provider == "voxcpm" and voice_clone_mode != "off":
                    # Zero-shot: no enrollment / voice_id. Clone directly from the local
                    # reference audio at synthesis time.
                    if local_ref_path.exists():
                        profile["voice_provider"] = "voxcpm"
                        profile["prompt_wav_path"] = str(local_ref_path)
                        profile["voice_model"] = settings.PCT_VOXCPM_MODEL
                        profile["enrollment_status"] = "enrolled"
                        profile["fallback_reason"] = None
                        speaker["voice_provider"] = "voxcpm"
                        speaker["voice_model"] = settings.PCT_VOXCPM_MODEL
                        speaker["enrollment_status"] = "enrolled"
                        speaker["fallback_reason"] = None
                        logger.info(
                            "Task %s: using local reference audio for VoxCPM zero-shot clone of speaker %s.",
                            ctx.task_id,
                            speaker_id,
                        )
                    else:
                        profile["enrollment_status"] = "fallback_no_ref"
                        profile["fallback_reason"] = "missing_reference_audio"
                        speaker["enrollment_status"] = "fallback_no_ref"
                        speaker["fallback_reason"] = "missing_reference_audio"
                        if voice_clone_mode == "required":
                            raise TaskPausedError(
                                f"Reference audio for speaker {speaker_id} is missing.",
                                provider="voxcpm",
                                reason_code="voice_reference_missing",
                                stage=self.stage,
                            )
                elif (
                    voice_clone_provider == "elevenlabs"
                    and voice_clone_mode != "off"
                    and profile.get("voice_provider") == "elevenlabs"
                    and profile.get("voice_id")
                ):
                    profile["voice_model"] = profile.get("voice_model") or settings.PCT_ELEVENLABS_TTS_MODEL
                    profile["enrollment_status"] = profile.get("enrollment_status") or "enrolled"
                    speaker["enrollment_status"] = profile["enrollment_status"]
                    logger.info("Task %s: reusing ElevenLabs voice %s for speaker %s.", ctx.task_id, profile["voice_id"], speaker_id)
                elif voice_clone_provider == "elevenlabs" and voice_clone_mode != "off":
                    if self.elevenlabs_provider is None:
                        raise TaskPausedError(
                            "ElevenLabs API key is not configured. Add it in Profile > API management.",
                            provider="elevenlabs",
                            reason_code="provider_credentials_missing",
                            stage=self.stage,
                        )
                    try:
                        voice_id = self.elevenlabs_provider.create_voice(
                            name=f"podflow-{ctx.task_id[:8]}-{speaker_id}",
                            reference_audio_path=str(local_ref_path),
                            labels={
                                "task_id": ctx.task_id,
                                "speaker": speaker_id,
                                "source": "podflow",
                            },
                        )
                        profile["voice_provider"] = "elevenlabs"
                        profile["voice_id"] = voice_id
                        profile["voice_model"] = settings.PCT_ELEVENLABS_TTS_MODEL
                        profile["enrollment_status"] = "enrolled"
                        profile["fallback_reason"] = None
                        speaker["voice_provider"] = "elevenlabs"
                        speaker["voice_id"] = voice_id
                        speaker["voice_model"] = settings.PCT_ELEVENLABS_TTS_MODEL
                        speaker["enrollment_status"] = "enrolled"
                        speaker["fallback_reason"] = None
                        logger.info("Task %s: created ElevenLabs voice %s for speaker %s.", ctx.task_id, voice_id, speaker_id)
                    except Exception as exc:
                        pause_error = pause_for_provider_error(
                            exc,
                            provider="elevenlabs",
                            stage=self.stage,
                            prefix="ElevenLabs voice cloning is unavailable",
                        )
                        if voice_clone_mode == "required":
                            if pause_error is not None:
                                raise pause_error from exc
                            raise self._required_provider_pause(
                                exc,
                                provider="elevenlabs",
                                prefix=f"ElevenLabs voice cloning failed for speaker {speaker_id}",
                            ) from exc
                        profile["enrollment_status"] = "fallback_failed"
                        profile["fallback_reason"] = "elevenlabs_clone_failed"
                        speaker["enrollment_status"] = "fallback_failed"
                        speaker["fallback_reason"] = "elevenlabs_clone_failed"
                        logger.warning(
                            "Task %s: ElevenLabs voice cloning failed for speaker %s. Falling back to preset voice.",
                            ctx.task_id,
                            speaker_id,
                            exc_info=True,
                        )
                elif (
                    settings.PCT_COSYVOICE_ENABLE_ENROLLMENT
                    and voice_clone_mode != "off"
                    and enrollment_service is not None
                    and not profile.get("voice_id")
                ):
                    presigned_url = run_sync(self.storage_service.get_presigned_url(ref_url, expires_in=3600))
                    if is_cloud_reachable_url(presigned_url):
                        try:
                            voice_id = enrollment_service.create_voice(
                                target_model=target_voice_model,
                                prefix=enrollment_prefix(ctx.task_id, speaker_id),
                                url=presigned_url,
                                max_prompt_audio_length=30.0,
                                enable_preprocess=True,
                            )
                            profile["voice_id"] = voice_id
                            profile["voice_model"] = target_voice_model
                            profile["voice_provider"] = "cosyvoice"
                            profile["enrollment_status"] = "enrolled"
                            speaker["voice_id"] = voice_id
                            speaker["voice_model"] = target_voice_model
                            speaker["voice_provider"] = "cosyvoice"
                            speaker["enrollment_status"] = "enrolled"
                            logger.info("Task %s: Enrolled voice %s for speaker %s.", ctx.task_id, voice_id, speaker_id)
                        except Exception as exc:
                            pause_error = pause_for_provider_error(
                                exc,
                                provider="dashscope",
                                stage=self.stage,
                                prefix="DashScope voice enrollment is unavailable",
                            )
                            if pause_error is not None:
                                raise pause_error from exc
                            profile["enrollment_status"] = "fallback_failed"
                            profile["fallback_reason"] = "cosyvoice_enrollment_failed"
                            speaker["enrollment_status"] = "fallback_failed"
                            speaker["fallback_reason"] = "cosyvoice_enrollment_failed"
                            if voice_clone_mode == "required":
                                raise self._required_provider_pause(
                                    exc,
                                    provider="dashscope",
                                    prefix=f"Voice enrollment failed for speaker {speaker_id}",
                                ) from exc
                            logger.warning(
                                "Task %s: Voice enrollment failed for speaker %s. Falling back to preset voice.",
                                ctx.task_id,
                                speaker_id,
                                exc_info=True,
                            )
                    else:
                        profile["enrollment_status"] = "fallback_unreachable_ref"
                        profile["fallback_reason"] = "reference_audio_unreachable"
                        speaker["enrollment_status"] = "fallback_unreachable_ref"
                        speaker["fallback_reason"] = "reference_audio_unreachable"
                        if voice_clone_mode == "required":
                            raise TaskPausedError(
                                f"Reference audio for speaker {speaker_id} is not cloud-reachable.",
                                provider="dashscope",
                                reason_code="voice_reference_unreachable",
                                stage=self.stage,
                            )
                        logger.info(
                            "Task %s: Reference audio for speaker %s is not cloud-reachable; using preset fallback voice.",
                            ctx.task_id,
                            speaker_id,
                        )
                elif profile.get("voice_id"):
                    profile["enrollment_status"] = profile.get("enrollment_status") or "enrolled"
                elif voice_clone_mode == "off":
                    profile["enrollment_status"] = "disabled"
                    profile["fallback_reason"] = "voice_clone_disabled"
                    speaker["enrollment_status"] = "disabled"
                    speaker["fallback_reason"] = "voice_clone_disabled"
            elif voice_clone_mode != "off":
                profile["enrollment_status"] = "fallback_no_ref"
                profile["fallback_reason"] = "missing_reference_audio"
                speaker["enrollment_status"] = "fallback_no_ref"
                speaker["fallback_reason"] = "missing_reference_audio"
                if voice_clone_mode == "required":
                    raise TaskPausedError(
                        f"Reference audio for speaker {speaker_id} is missing.",
                        provider=voice_clone_provider,
                        reason_code="voice_reference_missing",
                        stage=self.stage,
                    )

            if not profile.get("voice_id") and not profile.get("enrollment_status"):
                profile["enrollment_status"] = "fallback"
                profile["fallback_reason"] = profile.get("fallback_reason") or "preset_fallback"
                speaker["enrollment_status"] = "fallback"
                speaker["fallback_reason"] = profile["fallback_reason"]

            profiles[speaker_id] = profile

        return profiles

    def _build_synth_units(self, segments: list[dict]) -> list[SynthUnit]:
        units: list[SynthUnit] = []
        merge_enabled = settings.PCT_TTS_MERGE_SHORT_SEGMENTS
        max_seconds = max(1.0, settings.PCT_TTS_MERGE_MAX_SECONDS)
        max_gap = max(0.0, settings.PCT_TTS_MERGE_MAX_GAP_SECONDS)

        current: SynthUnit | None = None
        for index, segment in enumerate(segments):
            text = (segment.get("translation") or "").strip()
            if not text:
                continue
            speaker_id = str(segment.get("speaker_id") or "UNKNOWN")
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            if (
                merge_enabled
                and current is not None
                and current.speaker_id == speaker_id
                and start - current.end <= max_gap
                and end - current.start <= max_seconds
            ):
                current = SynthUnit(
                    segment_id=current.segment_id,
                    segment_ids=[*current.segment_ids, index],
                    speaker_id=speaker_id,
                    text=f"{current.text} {text}".strip(),
                    start=current.start,
                    end=end,
                )
                units[-1] = current
                continue
            current = SynthUnit(
                segment_id=index,
                segment_ids=[index],
                speaker_id=speaker_id,
                text=text,
                start=start,
                end=end,
            )
            units.append(current)
        return units

    def _load_existing_synth_unit(
        self,
        ctx: PipelineContext,
        unit: SynthUnit,
        temp_dir_path: Path,
    ) -> dict | None:
        segment = ctx.segments[unit.segment_id]
        object_name = segment.get("synth_audio_url")
        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        if not object_name and TaskStage.SYNTHESIZING.value not in invalidated_stages:
            object_name = f"{ctx.task_id}/synths/{unit.object_suffix}{SYNTH_AUDIO_EXTENSION}"
        if not object_name:
            return None

        try:
            if not run_sync(self.storage_service.object_exists(object_name)):
                return None

            suffix = Path(object_name).suffix or SYNTH_AUDIO_EXTENSION
            local_path = temp_dir_path / f"existing_synth_{unit.object_suffix}{suffix}"
            run_sync(self.storage_service.download_file(object_name, str(local_path)))
            duration = get_audio_duration(str(local_path))
            if duration <= 0:
                logger.warning(
                    "Task %s: existing synth segment %s has invalid duration; regenerating.",
                    ctx.task_id,
                    unit.object_suffix,
                )
                return None

            logger.info("Task %s: reusing existing TTS segment %s.", ctx.task_id, unit.object_suffix)
            segment["synth_audio_url"] = object_name
            return {
                "segment_id": unit.segment_id,
                "segment_ids": unit.segment_ids,
                "audio_url": object_name,
                "duration": duration,
                "speaker_id": unit.speaker_id,
                "tts_mode": "reused",
                "tts_voice": None,
            }
        except Exception:
            logger.warning(
                "Task %s: failed to reuse existing TTS segment %s; regenerating.",
                ctx.task_id,
                unit.object_suffix,
                exc_info=True,
            )
            return None

    def _synthesize_unit(
        self,
        ctx: PipelineContext,
        unit: SynthUnit,
        speaker_profile: dict | None,
        temp_dir_path: Path,
        rate_limiter: TokenBucketRateLimiter,
    ) -> dict:
        local_synth_out = temp_dir_path / f"synth_{unit.object_suffix}{SYNTH_AUDIO_EXTENSION}"
        logger.debug("Task %s: synthesizing unit %s for speaker %s.", ctx.task_id, unit.object_suffix, unit.speaker_id)
        rate_limiter.wait()
        synth_meta = self._synthesize_chunk(ctx, unit.text, str(local_synth_out), speaker_profile)

        if not local_synth_out.exists():
            raise FileNotFoundError("TTS did not create an output file.")

        actual_duration = get_audio_duration(str(local_synth_out))
        if actual_duration <= 0:
            raise RuntimeError("TTS output duration could not be parsed.")

        synth_object_name = f"{ctx.task_id}/synths/{unit.object_suffix}{SYNTH_AUDIO_EXTENSION}"
        run_sync(
            self.storage_service.upload_file(
                local_path=str(local_synth_out),
                object_name=synth_object_name,
                content_type=SYNTH_AUDIO_CONTENT_TYPE,
            )
        )

        for segment_id in unit.segment_ids:
            ctx.segments[segment_id]["synth_audio_url"] = synth_object_name

        delay = max(0.0, settings.PCT_DASHSCOPE_TTS_SEGMENT_DELAY_SECONDS)
        if delay > 0:
            time.sleep(delay)

        return {
            "segment_id": unit.segment_id,
            "segment_ids": unit.segment_ids,
            "audio_url": synth_object_name,
            "duration": actual_duration,
            "speaker_id": unit.speaker_id,
            "tts_mode": synth_meta["mode"],
            "tts_provider": synth_meta.get("provider"),
            "tts_voice": synth_meta["voice"],
            "tts_model": synth_meta["model"],
        }

    def process(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.segments:
            logger.warning("Task %s: segment list is empty. TTS skipped.", ctx.task_id)
            return ctx

        config = getattr(ctx, "config", None) or {}
        voice_clone_provider = normalize_voice_clone_provider(config.get("voice_clone_provider"))
        logger.info("Task %s: starting TTS stage with voice provider %s.", ctx.task_id, voice_clone_provider)
        ctx.synth_segments = []
        reused_segments = 0
        generated_segments = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            synth_units = self._build_synth_units(ctx.segments)
            total_segments = len(synth_units)
            tts_character_count = sum(len(unit.text) for unit in synth_units)
            progress_batch_size = max(1, settings.PCT_TTS_BATCH_SIZE)
            rate_limiter = TokenBucketRateLimiter(settings.PCT_DASHSCOPE_TTS_RPS)
            pending_units: list[SynthUnit] = []

            for unit in synth_units:
                existing_synth = self._load_existing_synth_unit(ctx, unit, temp_dir_path)
                if existing_synth is not None:
                    ctx.synth_segments.append(existing_synth)
                    reused_segments += 1
                    if reused_segments % progress_batch_size == 0 and reused_segments < total_segments:
                        self._report_items_progress(
                            ctx,
                            items_total=total_segments,
                            items_done=reused_segments,
                        )
                        self._report_progress(ctx, round(reused_segments * 100 / total_segments))
                    continue
                pending_units.append(unit)

            speaker_profiles: dict[str, dict] = {}
            if pending_units:
                self._configure_credentials(ctx)
                active_speaker_ids = {unit.speaker_id for unit in pending_units}
                speaker_profiles = self._build_speaker_profiles(ctx, temp_dir_path, active_speaker_ids)
                self._checkpoint_pipeline_state(ctx)

            speaker_profile_values = list(speaker_profiles.values()) if speaker_profiles else list(ctx.speakers or [])
            voice_metrics = {
                "voice_clone_provider": voice_clone_provider,
                "speaker_count": len(ctx.speakers or speaker_profile_values),
                "voice_clone_enrolled_count": len([
                    profile for profile in speaker_profile_values
                    if profile.get("voice_provider") == voice_clone_provider and profile.get("enrollment_status") == "enrolled"
                ]),
                "voice_clone_failed_count": len([
                    profile for profile in speaker_profile_values
                    if str(profile.get("enrollment_status") or "").startswith("fallback")
                ]),
                "voice_clone_fallback_count": len([
                    profile for profile in speaker_profile_values
                    if profile.get("fallback_reason")
                ]),
                "tts_character_count": tts_character_count,
            }
            self._report_items_progress(ctx, items_total=total_segments, items_done=reused_segments, metrics=voice_metrics)

            completed_units = reused_segments
            if total_segments:
                self._report_items_progress(ctx, items_total=total_segments, items_done=completed_units)
                self._report_progress(ctx, round(completed_units * 100 / total_segments))

            max_workers = max(1, int(settings.PCT_TTS_CONCURRENCY))
            if pending_units:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {
                        executor.submit(
                            self._synthesize_unit,
                            ctx,
                            unit,
                            speaker_profiles.get(unit.speaker_id),
                            temp_dir_path,
                            rate_limiter,
                        ): unit
                        for unit in pending_units
                    }
                    for future in as_completed(future_map):
                        unit = future_map[future]
                        try:
                            synth_result = future.result()
                        except TaskPausedError:
                            for pending in future_map:
                                pending.cancel()
                            raise
                        except Exception as exc:
                            logger.error(
                                "Task %s: error synthesizing unit %s: %s",
                                ctx.task_id,
                                unit.object_suffix,
                                exc,
                            )
                            raise RuntimeError(f"TTS synthesis failed for segment {unit.object_suffix}: {exc}") from exc

                        ctx.synth_segments.append(synth_result)
                        generated_segments += 1
                        completed_units += 1
                        if completed_units % progress_batch_size == 0 or completed_units == total_segments:
                            self._report_items_progress(
                                ctx,
                                items_total=total_segments,
                                items_done=completed_units,
                            )
                            self._checkpoint_pipeline_state(ctx)
                            self._report_progress(ctx, round(completed_units * 100 / total_segments))

        logger.info(
            "Task %s: TTS produced %s audio clips (%s reused, %s generated).",
            ctx.task_id,
            len(ctx.synth_segments),
            reused_segments,
            generated_segments,
        )
        if not ctx.synth_segments:
            raise RuntimeError("TTS synthesis failed for every segment; no audio clips were generated.")
        ctx.synth_segments.sort(key=lambda item: int(item.get("segment_id", 0)))
        mode_counts: dict[str, int] = {}
        provider_counts: dict[str, int] = {}
        for synth in ctx.synth_segments:
            mode = str(synth.get("tts_mode") or "unknown")
            provider = str(synth.get("tts_provider") or "unknown")
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        self._report_items_progress(
            ctx,
            items_total=len(ctx.synth_segments),
            items_done=len(ctx.synth_segments),
            metrics={
                "reused_segments": reused_segments,
                "generated_segments": generated_segments,
                "tts_mode_counts": mode_counts,
                "tts_provider_counts": provider_counts,
            },
        )
        return ctx
