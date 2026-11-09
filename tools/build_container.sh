#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
if docker buildx version >/dev/null 2>&1; then
    docker buildx build --platform linux/arm64 --load -f container/Dockerfile -t right-hand-rule:local .
else
    DOCKER_BUILDKIT=0 docker build --platform linux/arm64 -f container/Dockerfile -t right-hand-rule:local .
fi
mkdir -p dist
docker save right-hand-rule:local -o dist/submission.tar
sha256sum dist/submission.tar > dist/submission.tar.sha256
docker image inspect right-hand-rule:local --format '{{.Os}}/{{.Architecture}} {{json .Config.Entrypoint}}'
