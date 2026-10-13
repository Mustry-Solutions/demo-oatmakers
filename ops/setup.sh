#!/usr/bin/env bash
# Start the cloud demo with its simulated production data.
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/start-demo.sh" "$@"
