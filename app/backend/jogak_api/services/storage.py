from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from jogak_api.core.config import get_settings


def safe_suffix(filename: str | None, default: str = ".bin") -> str:
    if not filename or "." not in filename:
        return default
    suffix = Path(filename).suffix.lower()
    return suffix if len(suffix) <= 12 else default


async def save_upload(upload: UploadFile | None, subdir: str) -> str | None:
    if upload is None:
        return None
    settings = get_settings()
    target_dir = settings.asset_storage_root / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{uuid4().hex}{safe_suffix(upload.filename)}"
    with path.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            output.write(chunk)
    return str(path)


def asset_url(path: str | Path) -> str:
    settings = get_settings()
    raw = Path(path).resolve()
    storage_root = settings.asset_storage_root.resolve()
    try:
        relative = raw.relative_to(storage_root)
    except ValueError:
        relative = Path(path)
    return f"{str(settings.asset_base_url).rstrip('/')}/{relative.as_posix()}"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_job_dir(job_id: str) -> Path:
    settings = get_settings()
    job_dir = settings.job_storage_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir
