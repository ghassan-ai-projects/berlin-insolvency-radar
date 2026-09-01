"""File fingerprinting and mid-import mutation checks for legacy databases."""

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileFingerprint:
    """Content hash plus stat metadata identifying one exact file state."""

    sha256: str
    mtime: float
    size: int


class LegacyIntegrityError(RuntimeError):
    """Raised when the legacy file changes during an import.

    ``code`` carries the envelope error code (LEGACY_MUTATED or
    LEGACY_HASH_MISMATCH) for the failure result.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fingerprint_file(path: Path) -> FileFingerprint:
    """Hash and stat a file, reading in chunks to avoid OOM on large files."""
    stat = path.stat()
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return FileFingerprint(
        sha256=digest.hexdigest(), mtime=stat.st_mtime, size=stat.st_size
    )


def snapshot_unchanged(path: Path, fingerprint: FileFingerprint) -> bool:
    """Return True when size, mtime, and content hash still all match."""
    return fingerprint_file(path) == fingerprint


def verify_import_snapshot(path: Path, fingerprint: FileFingerprint) -> None:
    """Raise unless the legacy file is unchanged since the import started.

    Size or mtime drift raises LEGACY_MUTATED; a content-hash drift under
    unchanged metadata raises LEGACY_HASH_MISMATCH.
    """
    post = fingerprint_file(path)
    if post.size != fingerprint.size or post.mtime != fingerprint.mtime:
        raise LegacyIntegrityError(
            "LEGACY_MUTATED", "Legacy database was modified during import."
        )
    if post.sha256 != fingerprint.sha256:
        raise LegacyIntegrityError(
            "LEGACY_HASH_MISMATCH",
            "Legacy database content hash changed during import.",
        )
