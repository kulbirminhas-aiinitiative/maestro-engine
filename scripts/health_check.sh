#!/bin/bash
# Check health of all MAESTRO Engine services
# Usage: ./scripts/health_check.sh

set -e

SERVICES=(
    "coordinator:8002"
    "mcp:9800"
    "orchestration:8004"
    "rag:9803"
)

echo "🔍 Checking health of MAESTRO Engine services..."
echo ""

ALL_HEALTHY=true

for SERVICE in "${SERVICES[@]}"; do
    IFS=':' read -r NAME PORT <<< "$SERVICE"

    if curl -sf "http://localhost:$PORT/health" > /dev/null; then
        # Get latency
        LATENCY=$(curl -w "%{time_total}" -o /dev/null -s "http://localhost:$PORT/health" 2>&1 | grep -oE "[0-9.]+")
        LATENCY_MS=$(echo "$LATENCY * 1000" | bc | cut -d. -f1)

        if [ "$LATENCY_MS" -lt 100 ]; then
            echo "✅ $NAME: HEALTHY (${LATENCY_MS}ms)"
        elif [ "$LATENCY_MS" -lt 200 ]; then
            echo "⚠️  $NAME: DEGRADED (${LATENCY_MS}ms)"
        else
            echo "🐌 $NAME: SLOW (${LATENCY_MS}ms)"
        fi
    else
        echo "❌ $NAME: UNHEALTHY or not running"
        ALL_HEALTHY=false
    fi
done

echo ""

if [ "$ALL_HEALTHY" = true ]; then
    echo "✅ All services are healthy"
    exit 0
else
    echo "❌ Some services are unhealthy"
    exit 1
fi
