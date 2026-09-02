import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from src.config import settings
from src.services.user_api_key_service import ProviderCredentials

logger = logging.getLogger(__name__)


class ElevenLabsProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, response_text: str | None = None):
        self.status_code = status_code
        self.response_text = response_text
        self.error_code = f"HTTP{status_code}" if status_code else None
        detail = message
        if status_code:
            detail = f"{message}: HTTP {status_code}"
        if response_text:
            detail = f"{detail} - {response_text[:500]}"
        super().__init__(detail)

    @property
    def retryable(self) -> bool:
        return self.status_code in {408, 409, 425, 429, 500, 502, 503, 504}


class ElevenLabsVoiceProvider:
    def __init__(self, credentials: ProviderCredentials):
        self.api_key = credentials.api_key
        self.base_url = (credentials.base_url or settings.PCT_ELEVENLABS_BASE_URL).rstrip("/")
        self.timeout = max(1, settings.PCT_ELEVENLABS_TIMEOUT_SECONDS)
        self.max_retries = max(1, settings.PCT_ELEVENLABS_MAX_RETRIES)

    @property
    def headers(self) -> dict[str, str]:
        return {"xi-api-key": self.api_key}

    def create_voice(
        self,
        *,
        name: str,
        reference_audio_path: str,
        labels: dict[str, Any] | None = None,
    ) -> str:
        path = Path(reference_audio_path)
        data = {
            "name": name,
            "remove_background_noise": str(settings.PCT_ELEVENLABS_REMOVE_BACKGROUND_NOISE).lower(),
        }
        if labels:
            data["labels"] = json.dumps(labels, ensure_ascii=False)

        with path.open("rb") as audio_file:
            files = {
                "files": (
                    path.name,
                    audio_file,
                    "audio/wav",
                )
            }
            response = self._request(
                "POST",
                "/v1/voices/add",
                data=data,
                files=files,
            )

        payload = response.json()
        voice_id = payload.get("voice_id") if isinstance(payload, dict) else None
        if not voice_id:
            raise ElevenLabsProviderError(f"ElevenLabs did not return voice_id: {payload}")
        return str(voice_id)

    def delete_voice(self, voice_id: str) -> None:
        """Delete a cloned voice from the ElevenLabs account.

        Used by retention cleanup so IVC voices don't accumulate forever. A 404
        (voice already absent) surfaces as a non-retryable ``ElevenLabsProviderError``
        with ``status_code == 404`` and is treated as success by the caller.
        """
        self._request("DELETE", f"/v1/voices/{voice_id}")

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_id: str,
        output_path: str,
        model_id: str | None = None,
        output_format: str | None = None,
    ) -> None:
        response = self._request(
            "POST",
            f"/v1/text-to-speech/{voice_id}",
            params={"output_format": output_format or settings.PCT_ELEVENLABS_OUTPUT_FORMAT},
            json={
                "text": text,
                "model_id": model_id or settings.PCT_ELEVENLABS_TTS_MODEL,
            },
        )
        Path(output_path).write_bytes(response.content)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_exc: Exception | None = None
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(method, url, headers=self.headers, **kwargs)
                if response.status_code >= 400:
                    error = ElevenLabsProviderError(
                        "ElevenLabs request failed",
                        status_code=response.status_code,
                        response_text=response.text,
                    )
                    if not error.retryable:
                        raise error
                    last_exc = error
                else:
                    return response
            except ElevenLabsProviderError as exc:
                last_exc = exc
                if not exc.retryable or attempt >= self.max_retries:
                    raise
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break

            delay = max(0.0, settings.PCT_ELEVENLABS_RETRY_BACKOFF_SECONDS) * attempt
            if delay > 0:
                logger.warning("ElevenLabs request attempt %s/%s failed; retrying in %.1fs.", attempt, self.max_retries, delay)
                time.sleep(delay)

        if isinstance(last_exc, ElevenLabsProviderError):
            raise last_exc
        raise ElevenLabsProviderError(f"ElevenLabs request failed after {self.max_retries} attempt(s): {last_exc}") from last_exc


class VoxCpmProviderError(RuntimeError):
    """Raised when the self-hosted VoxCPM model is unavailable or synthesis fails."""

    error_code = None
    status_code = None


class VoxCpmVoiceProvider:
    """Self-hosted, zero-shot voice clone via VoxCPM (https://github.com/OpenBMB/VoxCPM).

    Unlike ElevenLabs/CosyVoice there is no enrollment step or persisted voice_id: the
    speaker's reference audio is passed directly at synthesis time, so nothing is stored
    on a third party and there is no cloud voice to clean up. The heavy model is loaded
    lazily and cached per process so the ``voxcpm`` package is never imported in mock/CI.
    """

    SAMPLE_RATE = 16000

    _model_cache: dict[str, Any] = {}
    _model_lock = threading.Lock()

    def __init__(self) -> None:
        self.model_id = settings.PCT_VOXCPM_MODEL
        self.device = settings.PCT_VOXCPM_DEVICE

    @classmethod
    def _get_model(cls, model_id: str):
        cached = cls._model_cache.get(model_id)
        if cached is not None:
            return cached
        with cls._model_lock:
            cached = cls._model_cache.get(model_id)
            if cached is not None:
                return cached
            try:
                from voxcpm import VoxCPM
            except ImportError as exc:  # pragma: no cover - depends on optional heavy dep
                raise VoxCpmProviderError(
                    "The voxcpm package is not installed. Run `pip install voxcpm soundfile` "
                    "on a GPU-capable worker to enable the VoxCPM voice clone provider."
                ) from exc
            logger.info("Loading VoxCPM model %s (one-time)...", model_id)
            model = VoxCPM.from_pretrained(model_id)
            cls._model_cache[model_id] = model
            logger.info("VoxCPM model %s loaded.", model_id)
            return model

    def synthesize_to_file(
        self,
        *,
        text: str,
        prompt_wav_path: str,
        output_path: str,
        prompt_text: str | None = None,
    ) -> None:
        model = self._get_model(self.model_id)
        generate_kwargs: dict[str, Any] = {
            "text": text,
            "prompt_wav_path": prompt_wav_path,
            "cfg_value": settings.PCT_VOXCPM_CFG_VALUE,
            "inference_timesteps": settings.PCT_VOXCPM_INFERENCE_TIMESTEPS,
            "normalize": settings.PCT_VOXCPM_NORMALIZE,
            "denoise": settings.PCT_VOXCPM_DENOISE,
            "retry_badcase": settings.PCT_VOXCPM_RETRY_BADCASE,
            "retry_badcase_max_times": settings.PCT_VOXCPM_RETRY_BADCASE_MAX_TIMES,
        }
        # VoxCPM clones the prompt timbre from audio alone; the reference transcript is
        # optional and we don't reliably have one for the trimmed reference slice, so it
        # is only passed when available.
        if prompt_text:
            generate_kwargs["prompt_text"] = prompt_text

        try:
            wav = model.generate(**generate_kwargs)
        except Exception as exc:  # pragma: no cover - depends on optional heavy dep
            raise VoxCpmProviderError(f"VoxCPM synthesis failed: {exc}") from exc

        self._export_mp3(wav, self.SAMPLE_RATE, output_path)

    def _export_mp3(self, wav, sample_rate: int, output_path: str) -> None:
        """Write the float waveform (numpy array) to ``output_path`` as MP3.

        Isolated so tests can stub it without pulling in soundfile/ffmpeg.
        """
        try:
            import soundfile as sf
        except ImportError as exc:  # pragma: no cover - depends on optional heavy dep
            raise VoxCpmProviderError(
                "The soundfile package is required to write VoxCPM output. Run `pip install soundfile`."
            ) from exc
        from pydub import AudioSegment

        tmp_wav = Path(output_path).with_suffix(".voxcpm.wav")
        sf.write(str(tmp_wav), wav, sample_rate)
        try:
            AudioSegment.from_file(str(tmp_wav)).export(output_path, format="mp3")
        finally:
            tmp_wav.unlink(missing_ok=True)
