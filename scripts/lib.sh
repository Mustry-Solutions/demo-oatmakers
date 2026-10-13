#!/bin/bash
# Shared helpers for setup.sh / scan.sh / reset-trial.sh.
# Sourced, not executed: . "$(dirname "$0")/lib.sh"

# Colors and shared constants below are consumed by the scripts that source
# this file, so shellcheck cannot see their use from here.
# shellcheck disable=SC2034

# Guard against direct execution.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  echo "scripts/lib.sh is meant to be sourced, not executed." >&2
  exit 1
fi

# Idempotent: only initialize once.
if [ "${_LAB_LIB_LOADED:-0}" = "1" ]; then
  return 0
fi
_LAB_LIB_LOADED=1

# Repo + scripts dir (works regardless of caller's cwd).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors. Suppress when stdout isn't a terminal or NO_COLOR is set.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[1;33m'
  NC=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; NC=''
fi

# Read a single KEY from a .env-style file (default: <repo>/.env).
# Strips optional single/double quotes around the value.
env_value() {
  local key="$1"
  local env_file="${2:-$PROJECT_ROOT/.env}"
  [ -f "$env_file" ] || { echo ""; return; }
  local v
  v="$(grep -E "^[[:space:]]*${key}=" "$env_file" | head -n1 | cut -d= -f2-)"
  v="${v%\"}"; v="${v#\"}"
  v="${v%\'}"; v="${v#\'}"
  printf '%s' "$v"
}

# A setting from the environment first, then .env, then a default. Same
# precedence docker compose uses for the port overrides.
setting() {
  local key="$1" default="$2" value
  value="${!key:-}"
  [ -n "$value" ] || value="$(env_value "$key")"
  printf '%s' "${value:-$default}"
}

# The two gateways of docker-compose.yaml.
gateway_port() {
  case "${1:-local}" in
    local) setting GATEWAY_PORT 8088 ;;
    test)  setting TEST_GATEWAY_PORT 8090 ;;
    *)     return 1 ;;
  esac
}

gateway_url() {
  local port
  port="$(gateway_port "${1:-local}")" || return 1
  printf 'http://localhost:%s' "$port"
}

gateway_container() {
  case "${1:-local}" in
    local) printf 'oatmakers-gateway' ;;
    test)  printf 'oatmakers-test-gateway' ;;
    *)     return 1 ;;
  esac
}

# Populate IGNITION_API_KEY: an exported value wins (CI sets it), otherwise
# the one scripts/generate-api-key.sh wrote into .env. Both local gateways
# accept the same key.
load_api_key_from_env() {
  if [ -n "${IGNITION_API_KEY:-}" ]; then
    return 0
  fi
  IGNITION_API_KEY="$(env_value IGNITION_API_KEY)"
  export IGNITION_API_KEY
}

# Returns 0 if IGNITION_API_KEY is empty or an obvious placeholder.
is_placeholder_api_key() {
  case "${IGNITION_API_KEY:-}" in
    ''|*replace-me*) return 0 ;;
    *) return 1 ;;
  esac
}

# Wait until a gateway is RUNNING and not COMMISSIONING. StatusPing reports
# {"state":"RUNNING","details":"COMMISSIONING"} while a boot-time module trust
# check runs, so a plain grep for RUNNING is not enough.
wait_gateway_running() {
  local url="$1" tries="${2:-60}" state=''
  for _ in $(seq 1 "$tries"); do
    state="$(curl -fsS -m 3 "$url/StatusPing" 2>/dev/null || true)"
    if echo "$state" | grep -q '"state":"RUNNING"' && ! echo "$state" | grep -q COMMISSIONING; then
      return 0
    fi
    sleep 5
  done
  LAST_GATEWAY_STATE="$state"
  return 1
}
