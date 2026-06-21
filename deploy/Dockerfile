# Azure Pricing Dashboard — FastAPI + Uvicorn (pinned, non-root).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Application code + static frontend.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Persisted JSON snapshots (mounted from Azure Files in production).
RUN mkdir -p /app/data/pricing

# Run as a non-root user, but allow the interpreter to bind the privileged port 443
# (so Cloudflare's proxy can connect to the origin over HTTPS in "Full" SSL mode).
# A self-signed cert terminates TLS on the container; Cloudflare "Full" accepts it.
RUN useradd --create-home --uid 10001 appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends libcap2-bin openssl \
    && rm -rf /var/lib/apt/lists/* \
    && setcap 'cap_net_bind_service=+ep' "$(readlink -f "$(command -v python3)")" \
    && mkdir -p /app/certs \
    && openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout /app/certs/key.pem -out /app/certs/cert.pem \
        -subj "/CN=azure-pricing" \
        -addext "subjectAltName=DNS:azure-pricing,DNS:localhost" \
    && chown -R appuser:appuser /app
USER appuser

ENV DATA_DIR=/app/data/pricing \
    DEFAULT_CURRENCY=USD \
    CACHE_TTL_SECONDS=3600

EXPOSE 443

# WORKDIR for the app so `src` is importable.
WORKDIR /app/backend

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,ssl,sys; ctx=ssl._create_unverified_context(); sys.exit(0 if urllib.request.urlopen('https://127.0.0.1:443/healthz',context=ctx).status==200 else 1)"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "443", \
     "--ssl-keyfile", "/app/certs/key.pem", "--ssl-certfile", "/app/certs/cert.pem"]
