import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import anyio
import structlog
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi_offline import FastAPIOffline
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from libreoffice_converter.converters import (
    doc_to_docx,
    docx_to_html,
    docx_to_html_zip,
    docx_to_pdf,
)
from libreoffice_converter.logging_config import configure_logging
from libreoffice_converter.queue import ConversionQueueMiddleware
from libreoffice_converter.utils import (
    cleanup_task,
    get_temp_dir,
    save_upload,
    sweep_temp_dir,
    validate_extension,
)

configure_logging()

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

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


FastAPIApp = FastAPIOffline if os.getenv("FASTAPI_OFFLINE", "false").lower() == "true" else FastAPI
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "true").lower() == "true"
docs_url = "/docs" if ENABLE_DOCS else None
redoc_url = "/redoc" if ENABLE_DOCS else None
app = FastAPIApp(
    title="LibreOffice Converter",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)

app.add_middleware(ConversionQueueMiddleware)
app.add_middleware(RequestIDMiddleware)
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
async def convert_doc_to_docx(request: Request, file: UploadFile = File(...)):
    validate_extension(file.filename, [".doc"])
    logger.info("convert.start", route="doc-to-docx", filename=file.filename)
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp, request.state.request_id)
    try:
        output_path = await doc_to_docx(input_path, tmp)
    except RuntimeError as exc:
        logger.error("convert.failed", route="doc-to-docx", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    logger.info("convert.success", route="doc-to-docx")
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
async def convert_docx_to_pdf(request: Request, file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    logger.info("convert.start", route="docx-to-pdf", filename=file.filename)
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp, request.state.request_id)
    try:
        output_path = await docx_to_pdf(input_path, tmp)
    except RuntimeError as exc:
        logger.error("convert.failed", route="docx-to-pdf", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    logger.info("convert.success", route="docx-to-pdf")
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
async def convert_docx_to_html(request: Request, file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    logger.info("convert.start", route="docx-to-html", filename=file.filename)
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp, request.state.request_id)
    try:
        output_path = await docx_to_html(input_path, tmp)
    except RuntimeError as exc:
        logger.error("convert.failed", route="docx-to-html", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    logger.info("convert.success", route="docx-to-html")
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
async def convert_docx_to_html_zip(request: Request, file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    logger.info("convert.start", route="docx-to-html-zip", filename=file.filename)
    original_stem = Path(file.filename or "output").stem
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp, request.state.request_id)
    try:
        zip_path = await docx_to_html_zip(input_path, tmp, original_stem)
    except RuntimeError as exc:
        logger.error("convert.failed", route="docx-to-html-zip", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    logger.info("convert.success", route="docx-to-html-zip")
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{original_stem}.zip",
        background=cleanup_task(zip_path),
    )
