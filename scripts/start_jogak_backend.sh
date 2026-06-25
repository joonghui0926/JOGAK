#!/usr/bin/env bash
set -euo pipefail

ROOT="/SSD/guest/chojoonghui/JOGAK"
LOG_DIR="${ROOT}/data/logs"
mkdir -p "${LOG_DIR}"

export PYTHONPATH="${ROOT}/app/backend"
exec /home/guest/anaconda3/envs/cjh_jogak/bin/uvicorn \
  jogak_api.main:app \
  --app-dir "${ROOT}/app/backend" \
  --host 0.0.0.0 \
  --port 8010
