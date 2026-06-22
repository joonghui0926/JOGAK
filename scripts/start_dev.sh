#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

source "${HOME}/anaconda3/etc/profile.d/conda.sh"
conda activate cjh_jogak

python app/backend/scripts/seed_database.py
uvicorn jogak_api.main:app --app-dir app/backend --host 0.0.0.0 --port 8000 &
API_PID=$!
npm --prefix app/frontend run dev -- --port 3000 &
WEB_PID=$!

trap 'kill ${API_PID} ${WEB_PID}' EXIT
wait
