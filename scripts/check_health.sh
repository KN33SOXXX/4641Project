#!/usr/bin/env bash
set -euo pipefail

cd "${SOCIAL_ROOT:-/home/user/social}"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export no_proxy="127.0.0.1,localhost,10.123.4.20"
export NO_PROXY="$no_proxy"
PYTHONDONTWRITEBYTECODE=1 python3 agent.py health
