"""
Auth API integration tests
"""
from src.config import settings


class TestSendSms:
    async def test_send_sms_success(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        resp = await client.post("/api/v1/auth/sms/send", json={"phone": "13800138000"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Code sent successfully"

    async def test_send_sms_missing_phone(self, client):
        resp = await client.post("/api/v1/auth/sms/send", json={})
        assert resp.status_code == 422

    async def test_send_sms_disabled_in_demo_mode(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "demo")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", False)

        resp = await client.post("/api/v1/auth/sms/send", json={"phone": "13800138000"})
        assert resp.status_code == 403


class TestSmsLogin:
    async def test_login_success(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        resp = await client.post("/api/v1/auth/sms/login", json={
            "phone": "13800138000",
            "code": "123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_code(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        resp = await client.post("/api/v1/auth/sms/login", json={
            "phone": "13800138000",
            "code": "000000",
        })
        assert resp.status_code == 401


class TestDemoLogin:
    async def test_demo_login_success(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "demo")
        monkeypatch.setattr(settings, "PCT_DEMO_USER_PHONE", "13800770000")
        monkeypatch.setattr(settings, "PCT_DEMO_USER_NICKNAME", "Shared Demo")

        resp = await client.post("/api/v1/auth/demo/login")

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_demo_login_disabled_when_not_in_demo_mode(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")

        resp = await client.post("/api/v1/auth/demo/login")
        assert resp.status_code == 403


class TestRefreshToken:
    async def test_refresh_success(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PCT_AUTH_MODE", "sms")
        monkeypatch.setattr(settings, "PCT_ENABLE_SMS_LOGIN", True)

        login_resp = await client.post("/api/v1/auth/sms/login", json={
            "phone": "13800002222",
            "code": "123456",
        })
        tokens = login_resp.json()

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_refresh_invalid_token(self, client):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid.token.value",
        })
        assert resp.status_code == 401
