#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
RHR_RUN_ID="${RHR_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$RHR_RUN_ID" =~ ^[A-Za-z0-9_-]+$ ]]
RHR_EPISODE="evidence/reproduction/$RHR_RUN_ID"
test ! -e "$RHR_EPISODE"
python tools/preflight.py
python -m pytest -q tests
python tools/freeze_v2.py --check
python harness/evaluate.py --scene maze --seed 0 --seconds 600 \
  --parameters config/navigation.json --control-config config/control.json \
  --transport --transport-config config/deployment.json \
  --latency-steps 0 --output "$RHR_EPISODE"
python tools/render.py --episode "$RHR_EPISODE" --output dist/reproduction.mp4
