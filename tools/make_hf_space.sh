#!/usr/bin/env bash
# Hugging Face Space 에 올릴 폴더(hf_space/)를 만든다. 이 폴더 안의 내용을 Space 에 그대로 올리면 된다.
set -euo pipefail
cd "$(dirname "$0")/.."
out=hf_space
mkdir -p "$out/backend"
cp deploy/hf-space/Dockerfile deploy/hf-space/README.md "$out/"
cp backend/pyproject.toml "$out/backend/"
cp -r backend/chartgame "$out/backend/"
find "$out/backend/chartgame" -name __pycache__ -type d -prune -exec rm -r {} +
echo "만들었어요: $out/"
