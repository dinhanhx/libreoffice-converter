import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from redis.asyncio import Redis

from libreoffice_converter.converters import (
    doc_to_docx,
    docx_to_html,
    docx_to_html_zip,
    docx_to_pdf,
)
from libreoffice_converter.queue import ConversionQueueMiddleware
from libreoffice_converter.utils import (
    cleanup_task,
    get_temp_dir,
    save_upload,
    sweep_temp_dir,
    validate_extension,
)

logger = logging.getLogger(__name__)

async def _periodic_sweep():
    while True:
        await anyio.sleep(int(os.getenv("SWEEP_INTERVAL_SECONDS", 600)))
        sweep_temp_dir(int(os.getenv("TEMP_MAX_AGE_SECONDS", 3600)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    app.state.redis = redis
    get_temp_dir()
    sweep_temp_dir()
    async with anyio.create_task_group() as tg:
        tg.start_soon(_periodic_sweep)
        yield
        tg.cancel_scope.cancel()
    await redis.aclose()


app = FastAPI(title="LibreOffice Converter", lifespan=lifespan)

app.add_middleware(ConversionQueueMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.post(
    "/convert/doc-to-docx",
    tags=["Conversions"],
    summary="Convert .doc → .docx",
    response_description="The converted .docx file as a binary download.",
)
@app.post("/convert", tags=["Legacy"])
async def convert_doc_to_docx(file: UploadFile = File(...)):
    validate_extension(file.filename, [".doc"])
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        output_path = await doc_to_docx(input_path, tmp)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    download_name = Path(file.filename or "output").stem + ".docx"
    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
        background=cleanup_task(output_path),
    )


@app.post(
    "/convert/docx-to-pdf",
    tags=["Conversions"],
    summary="Convert .docx → .pdf",
    response_description="The converted .pdf file as a binary download.",
)
@app.post("/docx2pdf", tags=["Legacy"])
async def convert_docx_to_pdf(file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        output_path = await docx_to_pdf(input_path, tmp)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    download_name = Path(file.filename or "output").stem + ".pdf"
    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=download_name,
        background=cleanup_task(output_path),
    )


@app.post(
    "/convert/docx-to-html",
    tags=["Conversions"],
    summary="Convert .docx → .html",
    response_description="The converted .html file as a binary download.",
)
async def convert_docx_to_html(file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        output_path = await docx_to_html(input_path, tmp)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    download_name = Path(file.filename or "output").stem + ".html"
    return FileResponse(
        path=output_path,
        media_type="text/html",
        filename=download_name,
        background=cleanup_task(output_path),
    )


@app.post(
    "/convert/docx-to-html-zip",
    tags=["Conversions"],
    summary="Convert .docx → .html (with assets as ZIP)",
    response_description="A ZIP file containing the .html file and its assets folder.",
)
async def convert_docx_to_html_zip(file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    original_stem = Path(file.filename or "output").stem
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        zip_path = await docx_to_html_zip(input_path, tmp, original_stem)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{original_stem}.zip",
        background=cleanup_task(zip_path),
    )
