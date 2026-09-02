import asyncio
import json
import logging

from src.config import settings
from src.core.exceptions import PCTException

logger = logging.getLogger(__name__)


class SMSService:
    """SMS sending wrapper.

    The provider is read from settings at call time (not cached) so tests and runtime
    config changes take effect. Mock mode just logs; ``aliyun`` sends via the Aliyun
    Dysmsapi SDK, lazily imported so it is never required in mock/CI environments.
    """

    @property
    def provider(self) -> str:
        return settings.PCT_SMS_PROVIDER

    async def send_verification_code(self, phone: str, code: str) -> bool:
        provider = self.provider
        if provider == "mock":
            logger.info("[MOCK SMS] Sending code %s to %s", code, phone)
            return True
        if provider == "aliyun":
            return await self._send_aliyun(phone, code)
        raise PCTException(f"Unsupported SMS provider: {provider}")

    async def _send_aliyun(self, phone: str, code: str) -> bool:
        access_key_id = settings.PCT_SMS_ACCESS_KEY_ID
        access_key_secret = (
            settings.PCT_SMS_ACCESS_KEY_SECRET.get_secret_value()
            if settings.PCT_SMS_ACCESS_KEY_SECRET
            else None
        )
        sign_name = settings.PCT_SMS_SIGN_NAME
        template_code = settings.PCT_SMS_TEMPLATE_CODE
        if not all([access_key_id, access_key_secret, sign_name, template_code]):
            raise PCTException(
                "Aliyun SMS is not fully configured. Set PCT_SMS_ACCESS_KEY_ID, "
                "PCT_SMS_ACCESS_KEY_SECRET, PCT_SMS_SIGN_NAME and PCT_SMS_TEMPLATE_CODE."
            )

        try:
            return await asyncio.to_thread(
                self._send_aliyun_sync,
                phone=phone,
                code=code,
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                sign_name=sign_name,
                template_code=template_code,
            )
        except PCTException:
            raise
        except Exception as exc:  # pragma: no cover - network/SDK failure path
            logger.error("Aliyun SMS send failed for %s: %s", phone, exc)
            raise PCTException("Failed to send SMS verification code.") from exc

    @staticmethod
    def _send_aliyun_sync(
        *,
        phone: str,
        code: str,
        access_key_id: str,
        access_key_secret: str,
        sign_name: str,
        template_code: str,
    ) -> bool:
        try:
            from alibabacloud_dysmsapi20170525 import models as dysms_models
            from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
            from alibabacloud_tea_openapi import models as open_api_models
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise PCTException(
                "The Aliyun SMS SDK is not installed. Run "
                "`pip install alibabacloud_dysmsapi20170525` on the backend to enable it."
            ) from exc

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config.endpoint = settings.PCT_SMS_ENDPOINT
        client = DysmsClient(config)
        request = dysms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=sign_name,
            template_code=template_code,
            template_param=json.dumps({"code": code}),
        )
        response = client.send_sms(request)
        body = response.body
        if getattr(body, "code", None) != "OK":
            message = getattr(body, "message", "unknown error")
            logger.error("Aliyun SMS rejected for %s: %s - %s", phone, getattr(body, "code", None), message)
            raise PCTException(f"SMS provider rejected the request: {message}")
        return True


sms_service = SMSService()
