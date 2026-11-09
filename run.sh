#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python -m pytest -q tests
python tools/freeze_evaluation.py --check
python harness/evaluate.py --scene maze --seed 0 --seconds 400 \
  --parameters config/navigation.json --transport --transport-config config/deployment.json \
  --latency-steps 0 --output evidence/reproduction
python tools/render.py --episode evidence/reproduction --output dist/reproduction.mp4
