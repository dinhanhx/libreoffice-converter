import os
import subprocess
from pathlib import Path

SOFFICE_TIMEOUT = int(os.getenv("SOFFICE_TIMEOUT", 300))


def _run_soffice(input_path: Path, output_dir: Path, convert_to: str) -> Path:
    """Run soffice --headless --convert-to and return the output file path."""
    result = subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            convert_to,
            "--outdir",
            str(output_dir),
            str(input_path),
        ],
        capture_output=True,
        text=True,
        timeout=SOFFICE_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)

    output_path = output_dir / (input_path.stem + "." + convert_to.split(":")[0])
    if not output_path.exists():
        raise RuntimeError(f"soffice did not produce expected output: {output_path}")
    return output_path


def doc_to_docx(input_path: Path, output_dir: Path) -> Path:
    return _run_soffice(input_path, output_dir, "docx")


def docx_to_pdf(input_path: Path, output_dir: Path) -> Path:
    return _run_soffice(input_path, output_dir, "pdf")


def docx_to_html(input_path: Path, output_dir: Path) -> Path:
    return _run_soffice(input_path, output_dir, "html")


def docx_to_html_zip(input_path: Path, output_dir: Path, original_stem: str) -> Path:
    """Convert docx to html with images and return path to a zip archive.

    soffice produces:
      <stem>.html
      <stem>_html_<hash>.png  (zero or more)

    The zip contains:
      <original_stem>.html
      <stem>_html_<hash>.png  (image filenames kept as-is)
    """
    import io
    import zipfile

    html_path = _run_soffice(input_path, output_dir, "html")
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
