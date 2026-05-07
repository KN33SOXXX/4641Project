#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/data2/social_workspace}"
SOCIAL_ROOT="${SOCIAL_ROOT:-/home/user/social}"
PYTHON_BIN="${PYTHON_BIN:-/home/user/miniconda3/envs/dl/bin/python}"
HOST="${OCR_HOST:-127.0.0.1}"
PORT="${OCR_PORT:-10004}"
SESSION="${OCR_TMUX_SESSION:-social_ocr}"
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
export WORKSPACE_ROOT SOCIAL_ROOT PYTHON_BIN HOST PORT PID_FILE LOG_FILE

mkdir -p "$WORKSPACE_ROOT"/{logs,models/PaddleOCR-VL,cache/huggingface,cache/paddle,cache/pip}

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "OCR tmux session already exists: $SESSION"
  exit 0
fi

cd "$SOCIAL_ROOT"
tmux new-session -d -s "$SESSION" \
  -e WORKSPACE_ROOT="$WORKSPACE_ROOT" \
  -e SOCIAL_ROOT="$SOCIAL_ROOT" \
  -e PYTHON_BIN="$PYTHON_BIN" \
  -e HOST="$HOST" \
  -e PORT="$PORT" \
  -e PID_FILE="$PID_FILE" \
  -e LOG_FILE="$LOG_FILE" \
  -e OCR_TMUX_SESSION="$SESSION" \
  -e CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES" \
  -e HF_HOME="$HF_HOME" \
  -e TRANSFORMERS_CACHE="$TRANSFORMERS_CACHE" \
  -e PIP_CACHE_DIR="$PIP_CACHE_DIR" \
  -e PADDLE_HOME="$PADDLE_HOME" \
  -e OCR_MODEL_ID="$OCR_MODEL_ID" \
  -e OCR_MODEL_DIR="$OCR_MODEL_DIR" \
  -e OCR_DEVICE="$OCR_DEVICE" \
  -e OCR_DTYPE="$OCR_DTYPE" \
  -e PYTHONDONTWRITEBYTECODE="$PYTHONDONTWRITEBYTECODE" \
  bash -lc '
set -euo pipefail
cd "$SOCIAL_ROOT"
exec > >(tee -a "$LOG_FILE") 2>&1
echo $$ > "$PID_FILE"
echo "Starting OCR service in tmux session ${OCR_TMUX_SESSION:-social_ocr} at http://$HOST:$PORT"
exec "$PYTHON_BIN" -m services.ocr_service --host "$HOST" --port "$PORT"
'

echo "Started OCR tmux session: $SESSION"
echo "PID file: $PID_FILE"
echo "Log: $LOG_FILE"
