import logging
from src.config import settings
from src.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

class WeChatOAuthService:
    """
    WeChat OAuth Authentication Service Wrapper.
    """
    def __init__(self):
        self.app_id = settings.PCT_WECHAT_APP_ID
        if settings.PCT_WECHAT_APP_SECRET:
            self.app_secret = settings.PCT_WECHAT_APP_SECRET.get_secret_value()
        else:
            self.app_secret = None

    async def get_openid_by_code(self, code: str) -> str:
        """
        Exchange WeChat authorization code for openid.
        Currently mocking this interaction.
        """
        if not self.app_id or not self.app_secret:
            logger.error("WeChat App ID or Secret not configured.")
            raise AuthenticationError("WeChat OAuth not properly configured.")
            
        logger.info(f"[MOCK WECHAT] Exchanging code {code} for openid.")
        # Mocking return openid
        if code == "invalid_code":
            raise AuthenticationError("Invalid WeChat code")
        return f"mock_wechat_openid_for_{code}"

wechat_oauth_service = WeChatOAuthService()
