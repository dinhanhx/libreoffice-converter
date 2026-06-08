import os
import subprocess
from pathlib import Path

SOFFICE_TIMEOUT = int(os.getenv("SOFFICE_TIMEOUT", 300))
UNOSERVER_PORT = os.getenv("UNOSERVER_PORT", "2003")


def _run_unoconvert(input_path: Path, output_path: Path, convert_to: str) -> Path:
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
        raise RuntimeError(result.stderr or result.stdout)
    if not output_path.exists():
        raise RuntimeError(f"unoconvert did not produce expected output: {output_path}")
    return output_path


def doc_to_docx(input_path: Path, output_dir: Path) -> Path:
    return _run_unoconvert(input_path, output_dir / (input_path.stem + ".docx"), "docx")


def docx_to_pdf(input_path: Path, output_dir: Path) -> Path:
    return _run_unoconvert(input_path, output_dir / (input_path.stem + ".pdf"), "pdf")


def docx_to_html(input_path: Path, output_dir: Path) -> Path:
    return _run_unoconvert(input_path, output_dir / (input_path.stem + ".html"), "html")


def docx_to_html_zip(input_path: Path, output_dir: Path, original_stem: str) -> Path:
    import io
    import zipfile

    html_path = _run_unoconvert(input_path, output_dir / (input_path.stem + ".html"), "html")
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
