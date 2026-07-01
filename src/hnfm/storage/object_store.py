"""MinIO/S3 client for media artifacts.

Object keys mirror the outputs/ tree (e.g. `hn/item/{id}/runs/{run}/segments/
{seg}/video/segment.mp4`), derived deterministically from local paths — so no
schema changes are needed and any artifact can be located from either side.

Publishing is non-fatal by design: a generation must never fail because the
object store is down; the local file remains the working copy.
"""

import logging
import mimetypes
import os
import threading
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client = None
_public_client = None
_bucket_ready = False

# mimetypes misses some of ours
_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".png": "image/png",
    ".vtt": "text/vtt",
    ".ass": "text/plain; charset=utf-8",
    ".json": "application/json",
}


def enabled() -> bool:
    return os.getenv("MEDIA_UPLOAD_ENABLED", "true").lower() == "true"


def bucket_name() -> str:
    return os.getenv("S3_BUCKET", "hnfm-media")


def _endpoint() -> str:
    return os.getenv("S3_ENDPOINT_URL", "http://localhost:9400")


def _public_endpoint() -> str:
    return os.getenv("S3_PUBLIC_URL", _endpoint())


def _make_client(endpoint: str):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "hnfm"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", "hnfm-minio-secret"),
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=3,
            retries={"max_attempts": 2},
        ),
    )


def get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = _make_client(_endpoint())
    return _client


def get_public_client():
    """Client configured against the browser-reachable endpoint.

    Presigned URLs embed the host in the signature, so URLs handed to the
    frontend must be signed against S3_PUBLIC_URL, not the in-network address.
    """
    global _public_client
    if _public_client is None:
        with _lock:
            if _public_client is None:
                _public_client = _make_client(_public_endpoint())
    return _public_client


def reset() -> None:
    """Forget cached clients (tests / env changes)."""
    global _client, _public_client, _bucket_ready
    with _lock:
        _client = None
        _public_client = None
        _bucket_ready = False


def ensure_bucket() -> None:
    global _bucket_ready
    if _bucket_ready:
        return
    client = get_client()
    try:
        client.head_bucket(Bucket=bucket_name())
    except Exception:
        client.create_bucket(Bucket=bucket_name())
    _bucket_ready = True


def key_for_path(local_path: str) -> Optional[str]:
    """Derive the object key from an outputs-relative local path."""
    if not local_path:
        return None
    p = str(local_path).replace(os.sep, "/")

    for env in ("OUTPUTS_DIR", "OUTPUTS_ROOT"):
        root = os.getenv(env)
        if root:
            root = root.rstrip("/") + "/"
            if p.startswith(root):
                return p[len(root):]

    marker = "outputs/"
    idx = p.find(marker)
    if idx != -1:
        return p[idx + len(marker):]
    return None


def content_type_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def publish_file(local_path: Optional[str]) -> Optional[str]:
    """Upload a finished artifact. Returns the object key, or None.

    Never raises — the object store must not be able to fail a generation.
    """
    if not enabled() or not local_path:
        return None
    if not os.path.exists(local_path):
        return None
    key = key_for_path(local_path)
    if not key:
        logger.warning(f"minio publish skipped: no outputs-relative key for {local_path}")
        return None
    try:
        ensure_bucket()
        get_client().upload_file(
            local_path,
            bucket_name(),
            key,
            ExtraArgs={"ContentType": content_type_for(local_path)},
        )
        return key
    except Exception as e:
        logger.warning(f"minio publish failed for {local_path} (non-fatal): {e}")
        return None


def object_exists(key: str) -> bool:
    if not enabled() or not key:
        return False
    try:
        get_client().head_object(Bucket=bucket_name(), Key=key)
        return True
    except Exception:
        return False


def presigned_url(key: str, expires_seconds: int = 3600) -> str:
    return get_public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name(), "Key": key},
        ExpiresIn=expires_seconds,
    )


def get_object_stream(key: str) -> Tuple[object, str]:
    """Streaming body + content type, for proxying through the API
    (subtitles need same-origin delivery for <track> CORS rules)."""
    obj = get_client().get_object(Bucket=bucket_name(), Key=key)
    ctype = obj.get("ContentType") or content_type_for(key)
    return obj["Body"], ctype
