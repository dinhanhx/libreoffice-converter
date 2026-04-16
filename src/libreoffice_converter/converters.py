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
