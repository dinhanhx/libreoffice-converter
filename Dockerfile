FROM python:3.10.20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY README.md .
COPY src/ src/

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -e .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn libreoffice_converter.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]
