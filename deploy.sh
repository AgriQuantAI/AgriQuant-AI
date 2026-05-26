#!/usr/bin/env bash
# AgriQuant AI — Production Deployment Script
# Usage: ./deploy.sh [environment]
set -euo pipefail

ENV="${1:-staging}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_LOG="logs/deploy_${TIMESTAMP}.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$DEPLOY_LOG"; }

log "Starting AgriQuant AI deployment — env=${ENV}"

# Pre-deploy checks
log "Running pre-deploy checks..."
python -m pytest tests/ -q --tb=short 2>&1 | tee -a "$DEPLOY_LOG" || {
    log "ERROR: Tests failed. Aborting deployment."
    exit 1
}

# Database migration
log "Applying schema migrations..."
psql "$DATABASE_URL" -f schema.sql 2>&1 | tee -a "$DEPLOY_LOG"

# Build and push Docker image
TAG="agriquant-ai:${ENV}-${TIMESTAMP}"
log "Building Docker image: $TAG"
docker build -t "$TAG" -t "agriquant-ai:${ENV}-latest" . 2>&1 | tee -a "$DEPLOY_LOG"

if [ "$ENV" = "production" ]; then
    log "Pushing to registry..."
    docker push "$TAG"
    docker push "agriquant-ai:${ENV}-latest"
fi

# Rolling restart
log "Performing rolling restart..."
docker-compose up -d --no-deps --build app api

# Health check
log "Waiting for health check..."
for i in $(seq 1 12); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "Health check passed after ${i}x5s"
        break
    fi
    sleep 5
done

log "Deployment complete: $TAG"
log "Log: $DEPLOY_LOG"
