#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/data2/social_workspace}"
PYTHON_BIN="${PYTHON_BIN:-/home/user/miniconda3/envs/dl/bin/python}"
MODEL_ID="${OCR_MODEL_ID:-PaddlePaddle/PaddleOCR-VL}"
MODEL_DIR="${OCR_MODEL_DIR:-$WORKSPACE_ROOT/models/PaddleOCR-VL}"

export MODELSCOPE_CACHE="$WORKSPACE_ROOT/cache/modelscope"
export PIP_CACHE_DIR="$WORKSPACE_ROOT/cache/pip"

mkdir -p "$MODEL_DIR" "$MODELSCOPE_CACHE" "$PIP_CACHE_DIR"

"$PYTHON_BIN" - <<PY
from modelscope.hub.snapshot_download import snapshot_download

path = snapshot_download(
    "${MODEL_ID}",
    cache_dir="${MODELSCOPE_CACHE}",
    local_dir="${MODEL_DIR}",
)
print(f"Downloaded ${MODEL_ID} to {path}")
PY
