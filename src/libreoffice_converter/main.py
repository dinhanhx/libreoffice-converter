from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from libreoffice_converter.converters import doc_to_docx, docx_to_html, docx_to_pdf
from libreoffice_converter.utils import (
    cleanup_task,
    get_temp_dir,
    save_upload,
    validate_extension,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_temp_dir()  # ensure temp dir exists at startup
    yield


app = FastAPI(title="LibreOffice Converter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/convert/doc-to-docx")
async def convert_doc_to_docx(file: UploadFile = File(...)):
    validate_extension(file.filename, [".doc"])
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        output_path = doc_to_docx(input_path, tmp)
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


@app.post("/convert/docx-to-pdf")
async def convert_docx_to_pdf(file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        output_path = docx_to_pdf(input_path, tmp)
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


@app.post("/convert/docx-to-html")
async def convert_docx_to_html(file: UploadFile = File(...)):
    validate_extension(file.filename, [".docx"])
    tmp = get_temp_dir()
    input_path = await save_upload(file, tmp)
    try:
        output_path = docx_to_html(input_path, tmp)
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
