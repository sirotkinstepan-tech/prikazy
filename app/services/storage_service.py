import logging
from dataclasses import dataclass

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_key: str
    version_id: str | None
    size_bytes: int
    mime_type: str


class ObjectStorageService:
    def __init__(self, settings: Settings, client: BaseClient | None = None):
        self.settings = settings
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.s3_bucket)
        except ClientError:
            logger.info("creating object storage bucket", extra={"bucket": self.settings.s3_bucket})
            self.client.create_bucket(Bucket=self.settings.s3_bucket)

    def upload_bytes(self, *, object_key: str, content: bytes, mime_type: str) -> StoredObject:
        self.ensure_bucket()
        response = self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=object_key,
            Body=content,
            ContentType=mime_type,
        )
        logger.info(
            "stored document object",
            extra={"bucket": self.settings.s3_bucket, "object_key": object_key},
        )
        return StoredObject(
            bucket=self.settings.s3_bucket,
            object_key=object_key,
            version_id=response.get("VersionId"),
            size_bytes=len(content),
            mime_type=mime_type,
        )

    def download_bytes(self, *, bucket: str, object_key: str) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read()
