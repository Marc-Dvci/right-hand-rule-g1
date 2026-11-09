#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
UV=${UV:-uv}
"$UV" venv "$ROOT/.venv" --python 3.12
"$UV" pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements.txt"
