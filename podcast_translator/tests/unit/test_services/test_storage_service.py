from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr

from src.services.storage_service import StorageService


class _AsyncClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestStorageService:
    def setup_method(self):
        StorageService._instance = None

    def teardown_method(self):
        StorageService._instance = None

    @patch("src.services.storage_service.settings")
    def test_uses_internal_endpoint_when_public_endpoint_missing(self, mock_settings):
        mock_settings.PCT_S3_ENDPOINT = "http://minio:9000/"
        mock_settings.PCT_S3_PUBLIC_ENDPOINT = None
        mock_settings.PCT_S3_BUCKET = "bucket"
        mock_settings.PCT_S3_ACCESS_KEY = SecretStr("admin")
        mock_settings.PCT_S3_SECRET_KEY = SecretStr("secret")

        service = StorageService()

        assert service.endpoint_url == "http://minio:9000"
        assert service.public_endpoint_url == "http://minio:9000"

    @patch("src.services.storage_service.settings")
    async def test_get_presigned_url_uses_public_endpoint(self, mock_settings):
        mock_settings.PCT_S3_ENDPOINT = "http://minio:9000/"
        mock_settings.PCT_S3_PUBLIC_ENDPOINT = "http://127.0.0.1:9000/"
        mock_settings.PCT_S3_BUCKET = "bucket"
        mock_settings.PCT_S3_ACCESS_KEY = SecretStr("admin")
        mock_settings.PCT_S3_SECRET_KEY = SecretStr("secret")

        service = StorageService()
        mock_client = AsyncMock()
        mock_client.generate_presigned_url = AsyncMock(return_value="http://signed-url")
        mock_session = MagicMock()
        mock_session.client.return_value = _AsyncClientContext(mock_client)
        service.session = mock_session

        url = await service.get_presigned_url("audio/result.mp3")

        assert url == "http://signed-url"
        mock_session.client.assert_called_once_with(
            "s3",
            endpoint_url="http://127.0.0.1:9000",
            aws_access_key_id="admin",
            aws_secret_access_key="secret",
        )
        mock_client.generate_presigned_url.assert_awaited_once_with(
            "get_object",
            Params={"Bucket": "bucket", "Key": "audio/result.mp3"},
            ExpiresIn=3600,
        )
