"""Upload generated videos to S3-compatible storage (R2 / AWS / RunPod)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote


def s3_configured() -> bool:
    return bool(os.environ.get("BUCKET_ENDPOINT_URL") and os.environ.get("BUCKET_NAME"))


def public_url(key: str) -> str:
    prefix = os.environ.get("BUCKET_PUBLIC_URL_PREFIX", "").rstrip("/")
    if prefix:
        return f"{prefix}/{quote(key)}"
    endpoint = os.environ.get("BUCKET_ENDPOINT_URL", "").rstrip("/")
    bucket = os.environ.get("BUCKET_NAME", "")
    return f"{endpoint}/{bucket}/{quote(key)}"


def upload_file(path: str | Path, key: str) -> str:
    """Upload via boto3 if present, otherwise via runpod rp_upload-style env.

    Returns a publicly fetchable HTTPS URL so Airtable can attach the file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if not s3_configured():
        raise RuntimeError(
            "S3/R2 is not configured. Set BUCKET_ENDPOINT_URL and BUCKET_NAME "
            "so the worker can give Airtable a public URL for the mp4."
        )

    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required to upload videos") from exc

    extra: dict[str, str] = {}
    region = os.environ.get("BUCKET_REGION") or os.environ.get("BUCKET_REGION_NAME") or "auto"
    extra["region_name"] = region
    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("BUCKET_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("BUCKET_ACCESS_KEY_ID")
        or os.environ.get("BUCKET_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("BUCKET_SECRET_ACCESS_KEY")
        or os.environ.get("BUCKET_SECRET_KEY"),
        **extra,
    )
    bucket = os.environ["BUCKET_NAME"]
    extra_args = {"ContentType": "video/mp4"}
    if os.environ.get("BUCKET_ACL"):
        extra_args["ACL"] = os.environ["BUCKET_ACL"]
    client.upload_file(str(path), bucket, key, ExtraArgs=extra_args)
    return public_url(key)
