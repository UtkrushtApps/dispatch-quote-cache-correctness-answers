#!/usr/bin/env bash
set -uo pipefail

cd /root/task 2>/dev/null || true

echo "[kill] Stopping docker compose services..."
docker compose down --remove-orphans || true

echo "[kill] Removing task-specific images..."
docker rmi -f redis:7-alpine || true

echo "[kill] Pruning docker system resources..."
docker system prune -a --volumes -f || true

echo "[kill] Removing task directory..."
rm -rf /root/task || true

echo "Cleanup completed successfully!"
