# libreoffice-converter

A FastAPI service that converts documents using LibreOffice (`unoserver`). Stateless — files are stored temporarily during processing only.

- `.doc` to `.docx`
- `.docx` to `.pdf`
- `.docx` to `.html`
- `.docx` to `.html` + assets as ZIP

## Requirements

- Docker + Docker Compose, or
- Python 3.10.20+, LibreOffice, and Redis installed locally

## Run with Docker Compose

```bash
docker compose up --build
```

Service is available at `http://localhost:9700`. Requests are proxied through Caddy.

## Run locally with uv

```bash
uv python pin 3.10
uv python install 3.10
uv venv --seed
source .venv/bin/activate
pip install -e .
uvicorn libreoffice_converter.main:app --host 0.0.0.0 --port 8000
```

Requires a local Redis instance and `unoserver` running separately.

## Architecture

```
client → Caddy :9700 → FastAPI :8000 (N uvicorn workers)
                            ↕                ↕
                        Redis :6379    unoserver :2003
                     (conversion queue)  (single shared process)
```

`entrypoint.sh` starts one supervised `unoserver` process (restarted on crash) and then execs `uvicorn`. This keeps a single LibreOffice/unoserver instance shared across all uvicorn workers, regardless of `UVICORN_WORKERS` — starting one unoserver per worker would collide on the same port.

Caddy enforces a max request body size on `/convert/*` endpoints (50 MB, 30 MB for `/convert/*`). `/health` and `/docs` have no Caddy limits applied.

### Conversion queue

All conversion endpoints are gated by a Redis-backed queue shared across all Uvicorn workers. Requests to `/health`, `/docs`, and `/openapi.json` bypass the queue entirely.

- If the number of waiting requests exceeds `MAX_QUEUE_SIZE`, the request is rejected immediately with `503`.
- If a request waits longer than `QUEUE_TIMEOUT_SECONDS` without acquiring a slot, it is rejected with `503`.

`503` responses include a `Retry-After: 5` header and a JSON body:

```json
{"detail": "Queue full", "active": 4, "queued": 20}
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FASTAPI_OFFLINE` | `false` | Serve Swagger/Redoc assets bundled offline instead of from a CDN |
| `ENABLE_DOCS` | `true` | Expose `/docs` and `/redoc` UIs (`/openapi.json` stays available either way) |
| `UVICORN_WORKERS` | `2` | Number of Uvicorn worker processes |
| `SOFFICE_TIMEOUT` | `300` | Timeout in seconds for each conversion |
| `MAX_UPLOAD_BYTES` | `52428800` | Max upload size in bytes (50 MB) |
| `MAX_CONCURRENT_CONVERSIONS` | `4` | Max simultaneous conversions across all workers |
| `SWEEP_INTERVAL_SECONDS` | `600` | How often the temp dir is swept |
| `TEMP_MAX_AGE_SECONDS` | `3600` | Max age of temp files before deletion |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `MAX_QUEUE_SIZE` | `40` | Max requests waiting in the queue |
| `UNOSERVER_PORT` | `2003` | Port unoserver listens on |
| `UNOSERVER_RESTART_DELAY_SECONDS` | `3` | Delay before restarting unoserver after it exits |
| `QUEUE_TIMEOUT_SECONDS` | `60` | Seconds a queued request waits before 503 |
| `QUEUE_POLL_INTERVAL_MS` | `200` | Polling interval while waiting for a slot |
| `PREP_DOCX` | `false` | Master switch for `.docx` preprocessing before conversion (always strips uniform table-cell borders when enabled) |
| `STRIP_RSIDS` | `false` | Also strip Word revision-save IDs (requires `PREP_DOCX=true`) |
| `FLATTEN_MERGED_CELLS` | `false` | Also flatten merged table cells (requires `PREP_DOCX=true`) |

## Endpoints

```
GET  /health
GET  /docs
POST /convert/doc-to-docx
POST /convert/docx-to-pdf
POST /convert/docx-to-html
POST /convert/docx-to-html-zip
```

Legacy aliases (still functional):

```
POST /convert   → /convert/doc-to-docx
POST /docx2pdf  → /convert/docx-to-pdf
```

## Example

```bash
curl -F "file=@report.docx" http://localhost:9700/convert/docx-to-pdf -o report.pdf
```
