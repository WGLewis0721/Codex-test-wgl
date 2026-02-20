"""AWS S3 service — document listing, download, and pre-signed URL generation."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".markdown"}


class S3Service:
    """Wrapper around the boto3 S3 client for document operations.

    Uses the credentials and region configured via :class:`~app.config.Settings`.
    If ``aws_access_key_id`` / ``aws_secret_access_key`` are empty the client
    falls back to the standard boto3 credential chain (instance profile, env
    vars, ``~/.aws/credentials``).
    """

    def __init__(self) -> None:
        session_kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._s3 = boto3.client("s3", **session_kwargs)
        self._bucket = settings.s3_bucket

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_documents(self) -> list[dict[str, Any]]:
        """List all supported documents in the configured S3 bucket.

        Uses paginated ``list_objects_v2`` so buckets with more than 1 000
        objects are handled correctly.

        Returns:
            List of dicts with keys: key, size, last_modified, content_type.
        """
        paginator = self._s3.get_paginator("list_objects_v2")
        documents: list[dict[str, Any]] = []

        for page in paginator.paginate(Bucket=self._bucket):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                suffix = Path(key).suffix.lower()
                if suffix not in _SUPPORTED_EXTENSIONS:
                    continue
                documents.append(
                    {
                        "key": key,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "content_type": _extension_to_content_type(suffix),
                    }
                )

        logger.info("Listed %d supported documents from S3 bucket=%s.", len(documents), self._bucket)
        return documents

    def download_document(self, key: str) -> tuple[Path, str]:
        """Download an S3 object to a temporary file.

        Args:
            key: S3 object key.

        Returns:
            Tuple of (local Path, content_type string).

        Raises:
            ClientError: If the object cannot be downloaded.
        """
        suffix = Path(key).suffix.lower()
        content_type = _extension_to_content_type(suffix)

        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        )
        tmp.close()
        local_path = Path(tmp.name)

        logger.debug("Downloading s3://%s/%s → %s", self._bucket, key, local_path)
        self._s3.download_file(self._bucket, key, str(local_path))
        return local_path, content_type

    def generate_presigned_url(self, key: str, expiry: int = 3600) -> str:
        """Generate a pre-signed GET URL for an S3 object.

        Args:
            key: S3 object key.
            expiry: URL validity period in seconds (default 1 hour).

        Returns:
            Pre-signed HTTPS URL string.

        Raises:
            ClientError: If URL generation fails.
        """
        url: str = self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )
        logger.debug("Generated pre-signed URL for key=%s (expiry=%ds).", key, expiry)
        return url

    def check_bucket_access(self) -> bool:
        """Verify that the configured bucket is accessible.

        Returns:
            ``True`` if the bucket can be listed, ``False`` otherwise.
        """
        try:
            self._s3.head_bucket(Bucket=self._bucket)
            return True
        except ClientError as exc:
            logger.warning("S3 bucket access check failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extension_to_content_type(suffix: str) -> str:
    """Map a file extension to a MIME content-type string."""
    mapping = {
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
    }
    return mapping.get(suffix.lower(), "application/octet-stream")
