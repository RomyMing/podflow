from pathlib import Path

import pytest

from src.pipeline.voice_providers import ElevenLabsProviderError, ElevenLabsVoiceProvider
from src.services.user_api_key_service import ProviderCredentials


class FakeResponse:
    status_code = 200
    text = ""
    content = b"audio-bytes"

    def __init__(self, payload=None):
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeClient:
    requests = []

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, headers=None, **kwargs):
        self.requests.append((method, url, headers, kwargs))
        if url.endswith("/v1/voices/add"):
            return FakeResponse({"voice_id": "voice-123"})
        return FakeResponse()


def test_elevenlabs_provider_creates_voice_and_synthesizes(monkeypatch):
    FakeClient.requests = []
    monkeypatch.setattr("src.pipeline.voice_providers.httpx.Client", FakeClient)
    provider = ElevenLabsVoiceProvider(
        ProviderCredentials(provider="elevenlabs", api_key="xi-test", base_url="https://api.elevenlabs.io")
    )
    scratch = Path("scratch")
    scratch.mkdir(exist_ok=True)
    reference = scratch / "elevenlabs_ref_test.wav"
    output = scratch / "elevenlabs_out_test.mp3"
    try:
        reference.write_bytes(b"wav")
        voice_id = provider.create_voice(name="podflow-test", reference_audio_path=str(reference))
        provider.synthesize_to_file(text="hello", voice_id=voice_id, output_path=str(output))

        assert voice_id == "voice-123"
        assert output.read_bytes() == b"audio-bytes"
        assert FakeClient.requests[0][0] == "POST"
        assert FakeClient.requests[0][1].endswith("/v1/voices/add")
        assert FakeClient.requests[1][1].endswith("/v1/text-to-speech/voice-123")
    finally:
        reference.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


def test_elevenlabs_provider_deletes_voice(monkeypatch):
    FakeClient.requests = []
    monkeypatch.setattr("src.pipeline.voice_providers.httpx.Client", FakeClient)
    provider = ElevenLabsVoiceProvider(
        ProviderCredentials(provider="elevenlabs", api_key="xi-test", base_url="https://api.elevenlabs.io")
    )

    provider.delete_voice("voice-123")

    assert FakeClient.requests[0][0] == "DELETE"
    assert FakeClient.requests[0][1].endswith("/v1/voices/voice-123")


def test_elevenlabs_provider_delete_voice_404_raises_non_retryable(monkeypatch):
    class NotFoundClient(FakeClient):
        def request(self, method, url, headers=None, **kwargs):
            self.requests.append((method, url, headers, kwargs))
            response = FakeResponse()
            response.status_code = 404
            response.text = "voice not found"
            return response

    NotFoundClient.requests = []
    monkeypatch.setattr("src.pipeline.voice_providers.httpx.Client", NotFoundClient)
    provider = ElevenLabsVoiceProvider(
        ProviderCredentials(provider="elevenlabs", api_key="xi-test", base_url="https://api.elevenlabs.io")
    )

    with pytest.raises(ElevenLabsProviderError) as excinfo:
        provider.delete_voice("missing-voice")

    assert excinfo.value.status_code == 404
    # Non-retryable -> only one attempt is made.
    assert len(NotFoundClient.requests) == 1
