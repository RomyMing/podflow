import logging
import threading

from aioboto3 import Session

from src.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
            return instance

    def __init__(self):
        if self._initialized:
            return
        self.endpoint_url = settings.PCT_S3_ENDPOINT.rstrip("/")
        self.public_endpoint_url = (settings.PCT_S3_PUBLIC_ENDPOINT or self.endpoint_url).rstrip("/")
        self.bucket = settings.PCT_S3_BUCKET
        self.access_key = (
            settings.PCT_S3_ACCESS_KEY.get_secret_value() if settings.PCT_S3_ACCESS_KEY else None
        )
        self.secret_key = (
            settings.PCT_S3_SECRET_KEY.get_secret_value() if settings.PCT_S3_SECRET_KEY else None
        )
        self.session = Session()
        self._initialized = True
        logger.info("StorageService initialized (singleton).")

    def _get_client(self, endpoint_url: str | None = None):
        return self.session.client(
            "s3",
            endpoint_url=endpoint_url or self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    async def ensure_bucket_exists(self):
        try:
            async with self._get_client() as s3:
                try:
                    await s3.head_bucket(Bucket=self.bucket)
                except Exception:
                    logger.info("Bucket %s not found, creating...", self.bucket)
                    await s3.create_bucket(Bucket=self.bucket)
                    logger.info("Bucket %s created successfully.", self.bucket)
        except Exception as exc:
            logger.error("Error ensuring bucket exists: %s", str(exc))

    async def upload_file_obj(
        self, file_obj, object_name: str, content_type: str = "audio/mpeg"
    ) -> str:
        await self.ensure_bucket_exists()
        try:
            async with self._get_client() as s3:
                await s3.upload_fileobj(
                    file_obj,
                    self.bucket,
                    object_name,
                    ExtraArgs={"ContentType": content_type},
                )
            logger.info("Successfully uploaded %s to bucket %s", object_name, self.bucket)
            return object_name
        except Exception as exc:
            logger.error("Error uploading file to storage: %s", str(exc))
            raise

    async def get_presigned_url(self, object_name: str, expires_in: int = 3600) -> str:
        if not object_name:
            return ""
        try:
            async with self._get_client(endpoint_url=self.public_endpoint_url) as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": object_name},
                    ExpiresIn=expires_in,
                )
        except Exception as exc:
            logger.error("Error generating presigned URL for %s: %s", object_name, str(exc))
            return ""

    async def download_file(self, object_name: str, dest_path: str) -> bool:
        try:
            async with self._get_client() as s3:
                await s3.download_file(self.bucket, object_name, dest_path)
            logger.info("Successfully downloaded %s to %s", object_name, dest_path)
            return True
        except Exception as exc:
            logger.error("Error downloading file %s from storage: %s", object_name, str(exc))
            raise

    async def object_exists(self, object_name: str) -> bool:
        if not object_name:
            return False
        try:
            async with self._get_client() as s3:
                await s3.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            error = response.get("Error", {}) or {}
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = str(error.get("Code") or "")
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return False
            logger.warning("Error checking object %s in storage: %s", object_name, str(exc))
            raise

    async def copy_object(self, source_object_name: str, target_object_name: str) -> str:
        await self.ensure_bucket_exists()
        try:
            async with self._get_client() as s3:
                await s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": source_object_name},
                    Key=target_object_name,
                )
            logger.info("Successfully copied %s to %s", source_object_name, target_object_name)
            return target_object_name
        except Exception as exc:
            logger.error(
                "Error copying %s to %s: %s",
                source_object_name,
                target_object_name,
                str(exc),
            )
            raise

    async def delete_object(self, object_name: str) -> None:
        if not object_name:
            return
        try:
            async with self._get_client() as s3:
                await s3.delete_object(Bucket=self.bucket, Key=object_name)
            logger.info("Successfully deleted %s from bucket %s", object_name, self.bucket)
        except Exception as exc:
            logger.error("Error deleting file %s from storage: %s", object_name, str(exc))
            raise

    async def list_objects(self, prefix: str) -> list[str]:
        keys: list[str] = []
        try:
            async with self._get_client() as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                    keys.extend(item["Key"] for item in page.get("Contents", []))
            return keys
        except Exception as exc:
            logger.error("Error listing objects with prefix %s: %s", prefix, str(exc))
            raise

    async def delete_prefix(self, prefix: str, *, keep_keys: set[str] | None = None) -> int:
        keep_keys = keep_keys or set()
        keys = [key for key in await self.list_objects(prefix) if key not in keep_keys]
        if not keys:
            return 0
        deleted = 0
        try:
            async with self._get_client() as s3:
                for index in range(0, len(keys), 1000):
                    batch = keys[index:index + 1000]
                    await s3.delete_objects(
                        Bucket=self.bucket,
                        Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                    )
                    deleted += len(batch)
            logger.info("Deleted %s object(s) with prefix %s", deleted, prefix)
            return deleted
        except Exception as exc:
            logger.error("Error deleting objects with prefix %s: %s", prefix, str(exc))
            raise

    async def check_connection(self) -> bool:
        try:
            async with self._get_client() as s3:
                await s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception as exc:
            logger.error("Storage health check failed: %s", str(exc))
            return False

    async def upload_file(self, local_path: str, object_name: str, content_type: str = "audio/wav") -> str:
        await self.ensure_bucket_exists()
        try:
            async with self._get_client() as s3:
                await s3.upload_file(
                    local_path,
                    self.bucket,
                    object_name,
                    ExtraArgs={"ContentType": content_type},
                )
            logger.info(
                "Successfully uploaded %s as %s to bucket %s",
                local_path,
                object_name,
                self.bucket,
            )
            return object_name
        except Exception as exc:
            logger.error("Error uploading file %s to storage: %s", local_path, str(exc))
            raise
