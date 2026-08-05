import logging
import os
import subprocess
from pathlib import Path

import anyio
from anyio.to_thread import run_sync
from docx import Document
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

SOFFICE_TIMEOUT = int(os.getenv("SOFFICE_TIMEOUT", 300))
UNOSERVER_PORT = os.getenv("UNOSERVER_PORT", "2003")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_CONVERSIONS", 2))
PREP_DOCX = os.getenv("PREP_DOCX", "false").lower() == "true"

_semaphore = anyio.Semaphore(MAX_CONCURRENT)


def _prep_docx(input_path: Path) -> None:
    doc = Document(str(input_path))
    removed = 0
    for table in doc.tables:
        tbl = table._tbl
        for tc in tbl.iter(qn("w:tc")):
            tcPr = tc.find(qn("w:tcPr"))
            if tcPr is not None:
                borders = tcPr.find(qn("w:tcBorders"))
                if borders is not None:
                    tcPr.remove(borders)
                    removed += 1
    doc.save(str(input_path))
    logger.info("prep_docx: removed %d tcBorders from %s", removed, input_path)


async def _prep_docx_async(input_path: Path) -> None:
    if PREP_DOCX:
        logger.debug("prep_docx: starting for %s", input_path)
        await run_sync(lambda: _prep_docx(input_path))


def _run_unoconvert(input_path: Path, output_path: Path, convert_to: str) -> Path:
    logger.info("unoconvert: %s -> %s (%s)", input_path, output_path, convert_to)
    result = subprocess.run(
        [
            "unoconvert",
            "--port", UNOSERVER_PORT,
            "--convert-to", convert_to,
            str(input_path),
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=SOFFICE_TIMEOUT,
    )
    if result.returncode != 0:
        logger.error("unoconvert failed for %s: %s", input_path, result.stderr or result.stdout)
        raise RuntimeError(result.stderr or result.stdout)
    if not output_path.exists():
        logger.error("unoconvert did not produce expected output: %s", output_path)
        raise RuntimeError(f"unoconvert did not produce expected output: {output_path}")
    logger.info("unoconvert: produced %s", output_path)
    return output_path


async def _run_unoconvert_async(input_path: Path, output_path: Path, convert_to: str) -> Path:
    async with _semaphore:
        return await run_sync(lambda: _run_unoconvert(input_path, output_path, convert_to))


async def doc_to_docx(input_path: Path, output_dir: Path) -> Path:
    return await _run_unoconvert_async(input_path, output_dir / (input_path.stem + ".docx"), "docx")


async def docx_to_pdf(input_path: Path, output_dir: Path) -> Path:
    await _prep_docx_async(input_path)
    return await _run_unoconvert_async(input_path, output_dir / (input_path.stem + ".pdf"), "pdf")


async def docx_to_html(input_path: Path, output_dir: Path) -> Path:
    await _prep_docx_async(input_path)
    return await _run_unoconvert_async(input_path, output_dir / (input_path.stem + ".html"), "html")


async def docx_to_html_zip(input_path: Path, output_dir: Path, original_stem: str) -> Path:
    import io
    import zipfile

    await _prep_docx_async(input_path)
    html_path = await _run_unoconvert_async(input_path, output_dir / (input_path.stem + ".html"), "html")
    image_paths = list(output_dir.glob(f"{input_path.stem}_html_*.png"))

    zip_path = output_dir / f"{input_path.stem}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(html_path, arcname=f"{original_stem}.html")
        for img in image_paths:
            zf.write(img, arcname=img.name)
    zip_path.write_bytes(buf.getvalue())

    html_path.unlink(missing_ok=True)
    for img in image_paths:
        img.unlink(missing_ok=True)

    return zip_path
