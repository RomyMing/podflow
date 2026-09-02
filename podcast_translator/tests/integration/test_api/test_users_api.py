"""
Users API 集成测试
"""
from unittest.mock import AsyncMock, patch


class TestGetMe:
    async def test_get_me_authenticated(self, authenticated_client, mock_user):
        resp = await authenticated_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone"] == mock_user.phone
        assert data["is_active"] is True

    async def test_get_me_unauthenticated(self, client):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401


class TestGetQuota:
    async def test_get_quota(self, authenticated_client, mock_user):
        resp = await authenticated_client.get("/api/v1/users/me/quota")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["used"] == 0
        assert data["remaining"] == 5


class TestUserApiKeys:
    async def test_api_key_crud_returns_masked_key(self, authenticated_client):
        put_resp = await authenticated_client.put(
            "/api/v1/users/me/api-keys/dashscope",
            json={"api_key": "sk-test-secret", "base_url": "https://dashscope.aliyuncs.com/api/v1"},
        )

        assert put_resp.status_code == 200
        data = put_resp.json()
        assert data["provider"] == "dashscope"
        assert data["masked_key"] == "sk-t...cret"
        assert "sk-test-secret" not in str(data)

        with patch(
            "src.services.provider_preflight_service.ProviderPreflightService.verify_credentials",
            new=AsyncMock(),
        ):
            verify_resp = await authenticated_client.post("/api/v1/users/me/api-keys/dashscope/verify")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["verified_at"] is not None

        list_resp = await authenticated_client.get("/api/v1/users/me/api-keys")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        delete_resp = await authenticated_client.delete("/api/v1/users/me/api-keys/dashscope")
        assert delete_resp.status_code == 204

    async def test_huggingface_token_crud_returns_masked_key(self, authenticated_client):
        put_resp = await authenticated_client.put(
            "/api/v1/users/me/api-keys/huggingface",
            json={"api_key": "hf_user_token_1234"},
        )

        assert put_resp.status_code == 200
        data = put_resp.json()
        assert data["provider"] == "huggingface"
        assert data["masked_key"] == "hf_u...1234"
        assert "hf_user_token_1234" not in str(data)
