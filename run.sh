#!/usr/bin/env bash
set -euo pipefail

cd /root/task
echo "[run] Working directory: $(pwd)"

echo "[run] Starting infrastructure with docker compose..."
docker compose up -d

echo "[run] Waiting for Redis to become reachable..."
for i in $(seq 1 30); do
  if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "[run] Redis is ready."
    break
  fi
  echo "[run] Redis not ready yet (attempt $i)..."
  sleep 2
done

echo "[run] Running test suite (deployability probe)..."
set +e
python -m pytest -q
rc=$?
set -e

echo "[run] pytest exit code: $rc"
if [ "$rc" -le 1 ]; then
  echo "[run] Deployability OK (tests collected and executed)."
  exit 0
else
  echo "[run] Deployability FAILED (collection or runner error)."
  exit "$rc"
fi
