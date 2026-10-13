#!/usr/bin/env bash
# Stop the cloud demo while retaining simulation and gateway state.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
case "${1:-}" in
  '') exec docker compose down;;
  --volumes|-v)
    echo 'This removes gateway state and simulated production history.' >&2
    if [ ! -t 0 ]; then echo 'Run interactively to confirm deleting the volumes.' >&2; exit 2; fi
    read -r -p 'Remove the demo volumes? [y/N] ' reply
    case "$reply" in y|Y) exec docker compose down --volumes;; *) exit 0;; esac;;
  *) echo 'Usage: ops/teardown.sh [--volumes]' >&2; exit 2;;
esac
