#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/data2/social_workspace}"
PYTHON_BIN="${PYTHON_BIN:-/home/user/miniconda3/envs/dl/bin/python}"

export HF_HOME="$WORKSPACE_ROOT/cache/huggingface"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export PIP_CACHE_DIR="$WORKSPACE_ROOT/cache/pip"
export PADDLE_HOME="$WORKSPACE_ROOT/cache/paddle"

mkdir -p "$WORKSPACE_ROOT"/{cache/huggingface,cache/pip,cache/paddle,models/PaddleOCR-VL,logs}

"$PYTHON_BIN" -m pip install -U "pillow" "transformers==4.55.0" "accelerate" "safetensors" "einops" "sentencepiece"

echo "OCR Python dependencies prepared for $PYTHON_BIN"
echo "Model cache root: $HF_HOME"
