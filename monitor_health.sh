#!/usr/bin/env bash
# AgriQuant AI — Continuous health monitoring
# Run as cron: */5 * * * * /app/monitor_health.sh
set -euo pipefail

API_URL="${AGRIQUANT_API_URL:-http://localhost:8000}"
ALERT_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

check_endpoint() {
    local endpoint="$1"
    local expected_status="${2:-200}"
    local response
    response=$(curl -sw "%{http_code}" -o /dev/null \
               --connect-timeout 5 --max-time 10 "$API_URL$endpoint" 2>/dev/null)
    if [ "$response" != "$expected_status" ]; then
        echo "ALERT: $endpoint returned $response (expected $expected_status)"
        if [ -n "$ALERT_WEBHOOK" ]; then
            curl -s -X POST "$ALERT_WEBHOOK" \
                -H 'Content-type: application/json' \
                --data "{\"text\":\"AgriQuant AI health check failed: $endpoint ($response)\"}"
        fi
        return 1
    fi
    return 0
}

check_endpoint "/health"
check_endpoint "/api/v1/signals"
check_endpoint "/api/v1/commodities/OJ/latest"
check_endpoint "/metrics"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Health checks passed"
