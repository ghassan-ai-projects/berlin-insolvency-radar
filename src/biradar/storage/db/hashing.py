"""Content hashing helpers."""

import hashlib


def compute_content_hash(data: str | bytes) -> str:
    """Compute SHA-256 hash of string or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"
