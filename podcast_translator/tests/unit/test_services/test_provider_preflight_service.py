import pytest

from src.core.provider_errors import TaskPausedError
from src.pipeline.context import TaskStage
from src.services.provider_preflight_service import ProviderPreflightResult, ProviderPreflightService
from src.services.user_api_key_service import ProviderCredentials


class TestProviderPreflightService:
    async def test_verify_credentials_uses_success_cache(self, monkeypatch):
        service = ProviderPreflightService()
        calls = 0

        async def fake_probe(credentials):
            nonlocal calls
            calls += 1

        monkeypatch.setattr(service, "_probe_openai_compatible", fake_probe)
        credentials = ProviderCredentials(provider="openai", api_key="sk-cache-test")

        first = await service.verify_credentials(credentials)
        second = await service.verify_credentials(credentials)

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert calls == 1

    async def test_verify_credentials_maps_invalid_key_to_pause(self, monkeypatch):
        service = ProviderPreflightService()

        async def fake_probe(credentials):
            raise RuntimeError("InvalidApiKey: check your API key")

        monkeypatch.setattr(service, "_probe_openai_compatible", fake_probe)
        credentials = ProviderCredentials(provider="openai", api_key="sk-invalid-test")

        with pytest.raises(TaskPausedError) as exc_info:
            await service.verify_credentials(credentials)

        assert exc_info.value.reason_code == "provider_invalid_api_key"
        assert exc_info.value.provider_error_code == "InvalidApiKey"

    async def test_verify_credentials_supports_huggingface(self, monkeypatch):
        service = ProviderPreflightService()
        calls = 0

        async def fake_probe(credentials):
            nonlocal calls
            calls += 1
            assert credentials.provider == "huggingface"

        monkeypatch.setattr(service, "_probe_huggingface", fake_probe)
        credentials = ProviderCredentials(provider="huggingface", api_key="hf_user_token_1234")

        result = await service.verify_credentials(credentials)

        assert result.provider == "huggingface"
        assert calls == 1

    async def test_verify_credentials_supports_elevenlabs(self, monkeypatch):
        service = ProviderPreflightService()
        calls = 0

        async def fake_probe(credentials):
            nonlocal calls
            calls += 1
            assert credentials.provider == "elevenlabs"

        monkeypatch.setattr(service, "_probe_elevenlabs", fake_probe)
        credentials = ProviderCredentials(provider="elevenlabs", api_key="xi-user-token")

        result = await service.verify_credentials(credentials)

        assert result.provider == "elevenlabs"
        assert calls == 1

    async def test_preflight_maps_saved_key_decryption_failure_to_pause(self, monkeypatch):
        service = ProviderPreflightService()

        async def fake_verify_storage(stage):
            return None

        async def fake_resolve_credentials(user_id, provider):
            raise ValueError("Saved deepseek API key cannot be decrypted.")

        monkeypatch.setattr(service, "_verify_local_runtime", lambda stage: None)
        monkeypatch.setattr(service, "_verify_storage", fake_verify_storage)
        monkeypatch.setattr(service, "_required_api_providers", lambda config, stage: ["deepseek"])
        monkeypatch.setattr(
            "src.services.provider_preflight_service.resolve_provider_credentials",
            fake_resolve_credentials,
        )

        with pytest.raises(TaskPausedError) as exc_info:
            await service.preflight_task(user_id=None, config={}, stage=TaskStage.TRANSLATING)

        assert exc_info.value.provider == "deepseek"
        assert exc_info.value.reason_code == "provider_invalid_api_key"
        assert exc_info.value.provider_error_code == "credential_decryption_failed"

    async def test_preflight_uses_saved_huggingface_token(self, monkeypatch):
        service = ProviderPreflightService()
        verified_providers = []

        async def fake_verify_storage(stage):
            return None

        async def fake_resolve_credentials(user_id, provider):
            assert provider == "huggingface"
            return ProviderCredentials(provider="huggingface", api_key="hf_user_token_1234")

        async def fake_verify_credentials(credentials):
            verified_providers.append(credentials.provider)
            return ProviderPreflightResult(provider=credentials.provider)

        monkeypatch.setattr(service, "_verify_local_runtime", lambda stage: None)
        monkeypatch.setattr(service, "_verify_storage", fake_verify_storage)
        monkeypatch.setattr(service, "verify_credentials", fake_verify_credentials)
        monkeypatch.setattr(
            "src.services.provider_preflight_service.resolve_provider_credentials",
            fake_resolve_credentials,
        )

        await service.preflight_task(user_id=None, config={}, stage=TaskStage.DIARIZING)

        assert verified_providers == ["huggingface"]


class TestUrlopenRetry:
    def test_retries_transient_then_succeeds(self, monkeypatch):
        import urllib.error

        from src.services import provider_preflight_service as mod

        calls = {"n": 0}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def flaky(request, timeout):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.URLError("SSL: UNEXPECTED_EOF_WHILE_READING")
            return FakeResp()

        monkeypatch.setattr(mod.urllib.request, "urlopen", flaky)
        monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

        resp = ProviderPreflightService._urlopen_with_retry(object(), timeout=5)
        assert resp.status == 200
        assert calls["n"] == 3

    def test_does_not_retry_http_error(self, monkeypatch):
        import urllib.error

        from src.services import provider_preflight_service as mod

        calls = {"n": 0}

        def auth_fail(request, timeout):
            calls["n"] += 1
            raise urllib.error.HTTPError("https://hf", 401, "unauthorized", {}, None)

        monkeypatch.setattr(mod.urllib.request, "urlopen", auth_fail)
        monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

        with pytest.raises(urllib.error.HTTPError):
            ProviderPreflightService._urlopen_with_retry(object(), timeout=5)
        assert calls["n"] == 1


class TestHttpxGetRetry:
    async def test_retries_transient_transport_error_then_succeeds(self, monkeypatch):
        import httpx

        from src.services import provider_preflight_service as mod

        calls = {"n": 0}

        class FakeResp:
            status_code = 200
            text = "ok"

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None):
                calls["n"] += 1
                if calls["n"] < 3:
                    raise httpx.ConnectError("connection reset")
                return FakeResp()

        monkeypatch.setattr(mod.httpx, "AsyncClient", FakeClient)
        monkeypatch.setattr(mod.asyncio, "sleep", _noop_async_sleep)

        resp = await ProviderPreflightService._httpx_get_with_retry("http://x/models", headers={}, timeout=5)
        assert resp.status_code == 200
        assert calls["n"] == 3


async def _noop_async_sleep(*_a, **_k):
    return None
