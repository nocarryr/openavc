"""Filesystem path-safety helpers shared across the API and cloud-tool layers."""

from pathlib import Path


def safe_path_within(base: Path, candidate: str) -> Path | None:
    """Resolve ``candidate`` under ``base`` and confirm it stays inside.

    Returns the resolved absolute path when ``candidate`` is contained within
    ``base``; returns ``None`` when it escapes — via ``..``, an absolute path,
    or a symlink that resolves outside. Callers decide how to surface the
    rejection (HTTP 400, an AI-tool error dict, skip-the-zip-member, etc.).
    """
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        return None
    return resolved
