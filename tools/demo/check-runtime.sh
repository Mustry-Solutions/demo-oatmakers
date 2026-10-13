#!/usr/bin/env bash
# Verify the running demo through its database and native Perspective page
# routes. Read-only: it changes nothing on the gateway or in the database.
#
#   tools/demo/check-runtime.sh            data is fresh and the routes answer
#   tools/demo/check-runtime.sh progress   also waits for the gateway's
#                                          continuity timer to advance
#
# Used by the Deploy workflow after a production deploy (a failure fails the
# run; rollback is a revert of the release PR) and by its six-hourly readiness
# check. No optional Web Dev module licence is required.
set -euo pipefail
container="${POSTGRES_CONTAINER:-cicd-capstone-postgres}"
url="${PUBLIC_URL:-https://cloud.mustrysolutions.com}"
mode="${1:-check}"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
read_health() {
  docker exec "$container" sh -c '
    user="${POSTGRES_USER:-}"
    if [ -n "${POSTGRES_USER_FILE:-}" ]; then user="$(cat "$POSTGRES_USER_FILE")"; fi
    psql -U "$user" -d "${POSTGRES_DB:-ignition}" -X -tA -v ON_ERROR_STOP=1 -c "SELECT oat_demo.health_live()"
  ' > "$tmp"
}
last_tick() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("lastTick",""))' "$tmp"; }
read_health
first="$(last_tick)"
if [ "$mode" = progress ]; then
  advanced=false
  for _ in $(seq 1 18); do
    sleep 5
    read_health
    if [ "$(last_tick)" != "$first" ]; then advanced=true; break; fi
  done
  test "$advanced" = true || { echo 'The gateway continuity timer did not advance.' >&2; exit 1; }
fi
python3 tools/demo/check-live.py "$url" --health-file "$tmp" --attempts 3
