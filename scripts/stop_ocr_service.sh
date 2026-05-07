#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/data2/social_workspace}"
PID_FILE="$WORKSPACE_ROOT/logs/ocr_service.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No OCR service PID file found"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped OCR service PID $PID"
else
  echo "OCR service PID $PID is not running"
fi
rm -f "$PID_FILE"
