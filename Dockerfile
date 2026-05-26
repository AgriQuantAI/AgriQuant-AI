# AgriQuant AI — Production Container
# Multi-stage build: builder + runtime
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libgdal-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements_additions.txt ./
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt && \
    pip install --user --no-cache-dir -r requirements_additions.txt

# ── Runtime stage ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="hello@agriquant.ai"
LABEL version="2.1.0"
LABEL description="AgriQuant AI — Multi-commodity agricultural weather intelligence"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libgdal32 curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --shell /bin/bash agriquant
WORKDIR /app

COPY --from=builder /root/.local /home/agriquant/.local
COPY --chown=agriquant:agriquant . .

USER agriquant

ENV PATH="/home/agriquant/.local/bin:${PATH}"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV AGRIQUANT_ENV=production

# Health check via dashboard API
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Default: run main monitoring loop
# Override with: docker run agriquant python demo.py
CMD ["python", "main.py"]
