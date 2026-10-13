#!/usr/bin/env bash
# Start this repository’s Oatmakers application and simulation.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEMO_HTTP_PORT="${DEMO_HTTP_PORT:-8088}"
exec "$root/tools/demo/start-local.sh"
