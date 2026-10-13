#!/usr/bin/env bash
# Reload the cloud demo project and configuration from this checkout.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export IGNITION_URL="${IGNITION_URL:-http://localhost:${DEMO_HTTP_PORT:-8088}}"
cd "$root"
case "${1:-both}" in
  projects|config|both) ;;
  *) echo 'Expected projects, config or both.' >&2; exit 2;;
esac
exec ops/scan.sh local
