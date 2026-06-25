#!/usr/bin/env bash
set -euo pipefail

ROOT="/SSD/guest/chojoonghui/JOGAK"
CLOUDFLARED="${ROOT}/bin/cloudflared"
CONFIG="${HOME}/.cloudflared/jogak-api.yml"

if [ ! -x "${CLOUDFLARED}" ]; then
  echo "cloudflared binary is missing: ${CLOUDFLARED}" >&2
  echo "Copy it from FinPilot or install cloudflared, then retry." >&2
  exit 1
fi

if [ ! -f "${CONFIG}" ]; then
  echo "Tunnel config is missing: ${CONFIG}" >&2
  echo "Create it from infra/cloudflared/config.example.yml after Cloudflare tunnel create." >&2
  exit 1
fi

exec "${CLOUDFLARED}" tunnel --config "${CONFIG}" run jogak-api
