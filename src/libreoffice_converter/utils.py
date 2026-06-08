import os
import shutil
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from starlette.background import BackgroundTask

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 50 * 1024 * 1024))  # 50 MB default
CHUNK_SIZE = 64 * 1024  # 64 KB

_TEMP_DIR: Path | None = None


def get_temp_dir() -> Path:
    global _TEMP_DIR
    if _TEMP_DIR is None:
        _TEMP_DIR = Path(tempfile.gettempdir()) / "libreoffice_converter"
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return _TEMP_DIR


def validate_extension(filename: str | None, allowed: list[str]) -> None:
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' not allowed. Expected: {allowed}",
        )


async def save_upload(file: UploadFile, dest_dir: Path) -> Path:
    suffix = Path(file.filename or "upload").suffix
    dest = dest_dir / (uuid4().hex + suffix)
    total = 0
    with dest.open("wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES} bytes",
                )
            f.write(chunk)
    return dest


def cleanup_task(*paths: Path) -> BackgroundTask:
    def _cleanup():
        for p in paths:
            p.unlink(missing_ok=True)

    return BackgroundTask(_cleanup)


def sweep_temp_dir(max_age_seconds: int = 3600) -> int:
    base = get_temp_dir()
    now = time.time()
    removed = 0
    for entry in base.iterdir():
        try:
            age = now - entry.stat().st_mtime
        except FileNotFoundError:
            continue
        if age < max_age_seconds:
            continue
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
        removed += 1
    return removed
