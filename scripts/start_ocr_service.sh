#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/data2/social_workspace}"
SOCIAL_ROOT="${SOCIAL_ROOT:-/home/user/social}"
PYTHON_BIN="${PYTHON_BIN:-/home/user/miniconda3/envs/dl/bin/python}"
HOST="${OCR_HOST:-127.0.0.1}"
PORT="${OCR_PORT:-10004}"
PID_FILE="$WORKSPACE_ROOT/logs/ocr_service.pid"
LOG_FILE="$WORKSPACE_ROOT/logs/ocr_service.log"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export HF_HOME="$WORKSPACE_ROOT/cache/huggingface"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export PIP_CACHE_DIR="$WORKSPACE_ROOT/cache/pip"
export PADDLE_HOME="$WORKSPACE_ROOT/cache/paddle"
export OCR_MODEL_ID="${OCR_MODEL_ID:-PaddlePaddle/PaddleOCR-VL}"
export OCR_MODEL_DIR="${OCR_MODEL_DIR:-$WORKSPACE_ROOT/models/PaddleOCR-VL}"
export OCR_DEVICE="${OCR_DEVICE:-cuda}"
export OCR_DTYPE="${OCR_DTYPE:-bfloat16}"
export PYTHONDONTWRITEBYTECODE=1

mkdir -p "$WORKSPACE_ROOT"/{logs,models/PaddleOCR-VL,cache/huggingface,cache/paddle,cache/pip}

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "OCR service already running with PID $(cat "$PID_FILE")"
  exit 0
fi

cd "$SOCIAL_ROOT"
nohup "$PYTHON_BIN" -m services.ocr_service --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Started OCR service PID $(cat "$PID_FILE") at http://$HOST:$PORT"
echo "Log: $LOG_FILE"
