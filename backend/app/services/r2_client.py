"""
R2 / Local PDF Storage Service.

Supports:
- Cloudflare R2 (S3-compatible) when R2 credentials are configured in .env.
- Automatic local filesystem fallback (uploads/) when R2 is not configured.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Base local uploads directory (backend/uploads)
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


def is_r2_configured() -> bool:
    """Return True if required Cloudflare R2 settings are present."""
    settings = get_settings()
    return bool(
        settings.r2_account_id and
        settings.r2_access_key_id and
        settings.r2_secret_access_key
    )


def _get_s3_client():
    """Build boto3 S3 client configured for Cloudflare R2 endpoint."""
    import boto3
    settings = get_settings()
    endpoint = settings.r2_endpoint_url or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


async def store_pdf(doc_id: str, filename: str, pdf_bytes: bytes) -> str:
    """
    Store PDF bytes either in Cloudflare R2 or in local uploads/ directory.
    Returns source_uri identifier (e.g. 'r2://knowwhere-pdfs/...' or 'local://...').
    """
    settings = get_settings()

    if is_r2_configured():
        try:
            s3 = _get_s3_client()
            key = f"documents/{doc_id}/{filename}"
            s3.put_object(
                Bucket=settings.r2_bucket_name,
                Key=key,
                Body=pdf_bytes,
                ContentType="application/pdf",
            )
            logger.info(f"[{doc_id}] Successfully uploaded to R2: {key}")
            return f"r2://{settings.r2_bucket_name}/{key}"
        except Exception as e:
            logger.warning(f"[{doc_id}] R2 upload failed ({e}); falling back to local storage.")

    # Local fallback
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_DIR / f"{doc_id}.pdf"
    with open(local_path, "wb") as f:
        f.write(pdf_bytes)

    logger.info(f"[{doc_id}] Saved PDF locally: {local_path}")
    return f"local://{doc_id}.pdf"


def get_pdf_bytes(doc_id: str, source_uri: str = "") -> Optional[bytes]:
    """Retrieve raw PDF bytes from R2 or local filesystem."""
    settings = get_settings()

    if source_uri.startswith("r2://") and is_r2_configured():
        try:
            s3 = _get_s3_client()
            # Extract bucket and key from r2://bucket/key
            parts = source_uri[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            response = s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except Exception as e:
            logger.warning(f"Failed to fetch from R2 ({e}), checking local fallback.")

    # Check local fallback
    local_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if local_path.exists():
        with open(local_path, "rb") as f:
            return f.read()

    return None


def get_view_url(doc_id: str, source_uri: str = "") -> str:
    """
    Generate an accessible URL to view/download the PDF.
    If R2 is configured and file is in R2, returns a presigned URL.
    Otherwise, returns local API route `/documents/{doc_id}/file`.
    """
    settings = get_settings()

    if source_uri.startswith("r2://") and is_r2_configured():
        try:
            s3 = _get_s3_client()
            parts = source_uri[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            presigned = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=3600,
            )
            return presigned
        except Exception as e:
            logger.warning(f"Could not generate R2 presigned URL: {e}")

    # Fallback to backend route
    return f"/documents/{doc_id}/file"
