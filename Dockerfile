FROM python:3.10.20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libreoffice \
        libreoffice-script-provider-python \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install unoserver with the system Python that ships the uno bridge.
# /usr/bin/python3 is the distro Python linked to the LibreOffice UNO module;
# /usr/local/bin/python3 is the container Python from the base image and lacks uno.
RUN /usr/bin/python3 -m pip install --no-cache-dir --break-system-packages unoserver

WORKDIR /app

COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY entrypoint.sh .

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -e .

EXPOSE 8000

CMD ["sh", "entrypoint.sh"]
