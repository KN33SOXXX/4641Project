#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/data2/social_workspace}"
PYTHON_BIN="${PYTHON_BIN:-/home/user/miniconda3/envs/dl/bin/python}"
DATASET_ID="${SCRATCHMATH_DATASET_ID:-songdj/ScratchMath}"
DATASET_DIR="${SCRATCHMATH_DATASET_DIR:-$WORKSPACE_ROOT/datasets/scratchmath}"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

export HF_HOME="$WORKSPACE_ROOT/cache/huggingface"
export HF_HUB_DISABLE_TELEMETRY=1
export PIP_CACHE_DIR="$WORKSPACE_ROOT/cache/pip"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

mkdir -p "$DATASET_DIR" "$HF_HOME" "$PIP_CACHE_DIR"

"$PYTHON_BIN" - <<PY
from pathlib import Path
from huggingface_hub import snapshot_download

dataset_id = "${DATASET_ID}"
dataset_dir = "${DATASET_DIR}"
cache_dir = "${HF_HOME}"
endpoint = "${HF_ENDPOINT}"

path = snapshot_download(
    repo_id=dataset_id,
    repo_type="dataset",
    endpoint=endpoint,
    local_dir=dataset_dir,
    cache_dir=cache_dir,
    max_workers=8,
)
print(f"Downloaded {dataset_id} from {endpoint} to {path}")
for file_path in sorted(Path(dataset_dir).rglob("*")):
    if file_path.is_file() and ".cache/huggingface" not in str(file_path):
        print(f"{file_path}\t{file_path.stat().st_size}")
PY
