# libreoffice-converter

A FastAPI service that converts documents using `soffice` (LibreOffice). Stateless — files are stored temporarily during processing only.

- `.doc` to `.docx`
- `.docx` to `.pdf`
- `.docx` to `.html`

## Requirements

- Docker + Docker Compose, or
- Python 3.10.20+ and LibreOffice installed locally

## Run with Docker Compose

```bash
docker compose up --build
```

Service is available at `http://localhost:8000`.

## Run locally with uv

```bash
uv python pin 3.10
uv python install 3.10
uv venv --seed
source .venv/bin/activate
pip install -e .
uvicorn libreoffice_converter.main:app --host 0.0.0.0 --port 8000
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `UVICORN_WORKERS` | `1` | Number of uvicorn worker processes |
| `SOFFICE_TIMEOUT` | `300` | Timeout in seconds for each soffice conversion |
| `MAX_UPLOAD_BYTES` | `52428800` | Max upload size in bytes (default 50 MB) |

## Endpoints

```
GET  /health
POST /convert/doc-to-docx
POST /convert/docx-to-pdf
POST /convert/docx-to-html
```

## Example

```bash
curl -F "file=@report.docx" http://localhost:8000/convert/docx-to-pdf -o report.pdf
```
