# SpectraCardio API — production image
# RESEARCH / EDUCATIONAL software, NOT a medical device.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# install deps first for better layer caching
COPY requirements-api.txt .
RUN pip install --upgrade pip && pip install -r requirements-api.txt

# app code
COPY . .

# run as non-root
RUN useradd -m app && chown -R app:app /app
USER app

EXPOSE 8000
# honor $PORT if the host assigns one (Render/Railway/Fly), else default 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
