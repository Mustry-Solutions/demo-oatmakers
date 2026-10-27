#!/bin/bash
# One-shot setup for the local Oatmakers stack:
#   - sanity-checks the host (docker compose v2, curl, git, python3)
#   - generates this clone's scan-API key into .env
#   - starts the database and applies the migrations (the demo simulation
#     needs its schema before the gateway's continuity timer runs)
#   - brings up the local gateway and, when .env sets LAB_USER, the Lab 07
#     Part 0 test stack (test gateway, its own database, your runner)
#   - fixes the one-time first-boot identity churn: commissioning invents a
#     "temp" idp/user source (password-reset semantics, because the repo
#     already carries security-properties). This promotes it to the
#     gitignored "default" (admin / password), restores the committed
#     security-properties, and restarts the gateway.
#   - checks that every gateway accepts the API key in .env, and restarts a
#     gateway once when it does not know the key yet (a new or rotated key:
#     gateways load token resources at boot only)
#
# Re-run safely: every step is idempotent. To rotate your API key, empty
# IGNITION_API_KEY in .env and run this script again.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

# shellcheck source=lib.sh
. scripts/lib.sh

# ---- Host preflight (WSL/permissions) --------------------------------------
# Refuses a sudo'd run, verifies the repo is not on the Windows filesystem
# (/mnt/c), reclaims root-owned leftovers, and exports LAB_GID so the
# gateway container writes files this user can still edit.
# shellcheck source=preflight.sh disable=SC1091
. scripts/preflight.sh
lab_preflight

# ---- prerequisites --------------------------------------------------------

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo -e "${RED}Error: '$1' is required but not installed.${NC}" >&2
    exit 1
  }
}

require_cmd docker
require_cmd curl
require_cmd git
require_cmd python3

if ! docker compose version >/dev/null 2>&1; then
  echo -e "${RED}Error: Docker Compose V2 plugin is required but not installed.${NC}" >&2
  exit 1
fi

echo -e "${GREEN}Oatmakers demo: local setup${NC}"
echo "================================"

# ---- Ignition resource hygiene --------------------------------------------
# The local gateway bind-mounts ./projects and ./services/config, so every UI
# interaction rewrites resource.json manifests inside your working tree,
# usually changing nothing but a timestamp and a signature.
#
#   .gitattributes routes those manifests through the textconv normalizer
#   below, which strips that metadata so `git diff` only shows real changes.
#   The pre-commit hook then reverts junk-only rewrites so they cannot be
#   committed. Hiding alone is not enough: an empty diff does not mean the
#   file on disk is unchanged.
#   The same hook runs iglint (the CI version and iglint.toml) on every
#   project the commit touches.
REPO_ROOT="$(pwd)"

configure_git_drivers() {
  git config diff.ignition-resource.textconv \
    "$REPO_ROOT/scripts/git-diff/normalize-ignition-resource-json.py"
}

install_git_hooks() {
  local repo_hooks_dir
  repo_hooks_dir="$(git rev-parse --git-path hooks 2>/dev/null)" || return 0
  local source_dir="$REPO_ROOT/scripts/git-hooks"
  [ -d "$source_dir" ] || return 0
  mkdir -p "$repo_hooks_dir"
  ln -sf "$source_dir/pre-commit" "$repo_hooks_dir/pre-commit"
}

configure_git_drivers
install_git_hooks

# ---- This clone's scan-API key ---------------------------------------------
# Generates IGNITION_API_KEY into .env (creating .env from .env.example when
# missing) and writes the hash-only CICD-APIKEY token resource into
# services/config (gitignored). The local gateway loads it from the bind
# mount; the Part 0 seed below copies the same resource into the test
# gateway's volume before its first boot.
scripts/generate-api-key.sh
pf_persist_lab_gid

# ---- Part 0 opt-in: is the personal test pair configured? -----------------
LAB_USER_VALUE="$(env_value LAB_USER)"
PROFILE_ARGS=()
if [ -n "$LAB_USER_VALUE" ] && [ "$LAB_USER_VALUE" != "yourname" ]; then
  case "$LAB_USER_VALUE" in
    *[!a-z0-9-]*)
      echo -e "${RED}LAB_USER='$LAB_USER_VALUE' in .env: use lowercase letters, digits and dashes only.${NC}" >&2
      echo "It becomes part of a runner label and a container name." >&2
      exit 1
      ;;
  esac
  PROFILE_ARGS=(--profile test)
fi
compose() { docker compose ${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"} "$@"; }

# ---- Part 0: seed the test gateway's API token BEFORE its first boot --------
# The scan API only accepts tokens the gateway has LOADED, and a deploy cannot
# scan its own token in. The test gateway has no bind mount, so we write into
# its named volume with a throwaway container.
#
# The collection manifest must come along: on first boot the gateway creates
# the `core` collection and refuses a non-empty dir without a manifest.
#
# On later runs the token is replaced when the key in .env changed (a
# rotation); the key check further down restarts the gateway to load it.
#
# Deliberately NOT seeded: security-properties. A gateway that boots with a
# pre-existing security-properties treats commissioning as a password reset
# and stamps a "temp" identity instead of "default", and the deploy keeps only
# the identity named "default", which would end in an admin lockout. The
# committed security-properties arrives with the first deploy instead; the
# workflow's 401/403 self-heal restart loads it.
seed_test_gateway() {
  local project vol
  project="$(docker compose config --format json 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))')"
  vol="${project}_test-gateway-data"

  # Create the container (and thereby the volume) WITHOUT booting it: if the
  # gateway wins this race, commissioning runs before the token is on disk.
  compose create test-gateway >/dev/null 2>&1 || true
  docker volume inspect "$vol" >/dev/null 2>&1 || return 0

  local token_rel=resources/core/ignition/api-token
  if docker run --rm -v "$vol:/d" alpine:3 \
       test -d "/d/config/$token_rel" 2>/dev/null; then
    # Already seeded: replace the token only when the key in .env changed.
    local want have
    want="$(token_hash < "services/config/$token_rel/$API_TOKEN_NAME/config.json")"
    have="$(docker run --rm -v "$vol:/d" alpine:3 \
      cat "/d/config/$token_rel/$API_TOKEN_NAME/config.json" 2>/dev/null | token_hash)"
    [ -n "$want" ] && [ "$want" = "$have" ] && return 0
    echo "Your API key changed: replacing the test gateway's token in $vol..."
    docker run --rm -v "$vol:/d" -v "$PWD/services/config/$token_rel:/seed:ro" alpine:3 \
      sh -c "rm -rf '/d/config/$token_rel' && mkdir -p '/d/config/$token_rel' \
             && cp -R /seed/. '/d/config/$token_rel/' && chown -R 2003:0 '/d/config/$token_rel'"
    return 0
  fi

  echo "Seeding the test gateway's API token before its first boot..."
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/resources/core/ignition"
  cp services/config/resources/core/config-mode.json "$tmp/resources/core/"
  cp -R "services/config/$token_rel" "$tmp/resources/core/ignition/"
  docker run --rm -v "$vol:/d" -v "$tmp:/seed:ro" alpine:3 \
    sh -c 'mkdir -p /d/config && cp -R /seed/. /d/config/ && chown -R 2003:0 /d'
  rm -rf "$tmp"
  echo "  seeded api-token into $vol"
}

# The tokenHash of an api-token config.json on stdin (empty when unreadable).
token_hash() {
  python3 -c 'import json,sys
try: print(json.load(sys.stdin)["settings"]["tokenHash"])
except Exception: pass'
}

load_api_key_from_env
API_TOKEN_NAME="${IGNITION_API_KEY%%:*}"

if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  seed_test_gateway
fi

# ---- database first, then the migrations ----------------------------------
# The local database only. Your test gateway's database (test-postgres) is
# migrated by your test workflow, like production's by Deploy.
docker compose up -d postgres
echo -n "Waiting for the database "
for _ in $(seq 1 60); do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' "$(db_container local)" 2>/dev/null)" = healthy ]; then
    echo " up."
    break
  fi
  echo -n "."
  sleep 2
done
# A failure here does not stop the setup: the usual cause is a migration you
# applied on another branch, and the gateways (and a key rotation) must still
# come up. The fix is on that branch.
if ! scripts/migrate.sh up; then
  echo -e "${YELLOW}The local database did not migrate (see above). Carrying on with the gateways.${NC}"
  echo "  'no migration found for version N': your local database ran migration N on"
  echo "  another branch. Switch to that branch, run scripts/migrate.sh down 1, switch"
  echo "  back and run scripts/migrate.sh up."
fi

# ---- the gateways (and your runner) ----------------------------------------
compose up -d

wait_running() {
  local which="$1" url container
  url="$(gateway_url "$which")"
  container="$(gateway_container "$which")"
  echo "Waiting for the $which gateway at $url to reach RUNNING..."
  if wait_gateway_running "$url" 72; then
    echo "  up."
    return 0
  fi
  if echo "${LAST_GATEWAY_STATE:-}" | grep -q COMMISSIONING; then
    echo -e "${RED}The $which gateway is stuck in COMMISSIONING: it waits for a module${NC}" >&2
    echo -e "${RED}certificate or licence acceptance. Open $url to see what it asks for.${NC}" >&2
  else
    echo -e "${RED}The $which gateway did not reach RUNNING. Check: docker logs $container${NC}" >&2
  fi
  exit 1
}
wait_running local
if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  wait_running test
fi

# ---- one-time first-boot identity fix --------------------------------------

IG=services/config/resources/core/ignition

if [ -d "$IG/user-source/temp" ] || [ -d "$IG/identity-provider/temp" ]; then
  echo "First boot detected: replacing the commissioning's temp identity..."

  # temp user source -> default (files unchanged, so its signature stays valid)
  rm -rf "$IG/user-source/default"
  mv "$IG/user-source/temp" "$IG/user-source/default"

  # temp identity provider -> default, repointed at the "default" user source.
  # Editing config.json invalidates the recorded signature, so drop it: the
  # gateway accepts unsigned resources.
  rm -rf "$IG/identity-provider/default"
  mv "$IG/identity-provider/temp" "$IG/identity-provider/default"
  python3 - "$IG/identity-provider/default" <<'EOF'
import json, sys, os
d = sys.argv[1]
cfg_path = os.path.join(d, 'config.json')
cfg = json.load(open(cfg_path))
cfg['settings']['userSource'] = 'default'
json.dump(cfg, open(cfg_path, 'w'), indent=2, sort_keys=True)
res_path = os.path.join(d, 'resource.json')
res = json.load(open(res_path))
res['description'] = 'Local identity provider backed by the "default" user source.'
res['attributes'].pop('lastModificationSignature', None)
json.dump(res, open(res_path, 'w'), indent=2)
EOF

  # put the committed permission policy back and restart onto it
  git checkout -- "$IG/security-properties"
  docker compose restart gateway
  wait_running local
else
  # nothing to promote; still make sure commissioning churn isn't lingering
  git checkout -- "$IG/security-properties" 2>/dev/null || true
fi

# ---- do the gateways accept this clone's API key? ---------------------------
# A gateway loads api-token resources at boot only. After a key rotation (or a
# token written while it ran) it answers 401 until it restarts, so restart it
# once and check again. The test gateway may answer 403 until your first test
# deploy ships the committed security-properties: the key is known, the
# permission arrives with that deploy.

# The key's status code, retried while the gateway's API is still starting.
key_status_when_ready() {
  local url="$1" code=''
  for _ in $(seq 1 24); do
    code="$(api_key_status "$url")"
    case "$code" in
      000|400|5??) sleep 5 ;;
      *) break ;;
    esac
  done
  printf '%s' "$code"
}

ensure_api_key() {
  local which="$1" url container code
  url="$(gateway_url "$which")"
  container="$(gateway_container "$which")"
  code="$(key_status_when_ready "$url")"
  if [ "$code" = "401" ]; then
    echo "The $which gateway does not know the API key in .env yet; restarting it once to load it..."
    docker restart "$container" >/dev/null
    wait_running "$which"
    code="$(key_status_when_ready "$url")"
  fi
  case "$which:$code" in
    *:2??)
      echo "  API key accepted by the $which gateway (HTTP $code)." ;;
    test:403)
      echo "  API key known to the test gateway (HTTP 403 until your first test deploy grants it scans)." ;;
    *)
      echo -e "${RED}The $which gateway answered HTTP $code to the API key in .env.${NC}" >&2
      echo "Check: docker logs $container" >&2
      exit 1 ;;
  esac
}
ensure_api_key local
if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  ensure_api_key test
fi

# ---- Part 0: is your runner listening? -------------------------------------
# Contributors cannot open Settings -> Actions -> Runners, so the runner's own
# log is the place to look.
if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  runner="$(stack_name)-test-runner-$LAB_USER_VALUE"
  echo -n "Waiting for your runner ($runner) to listen for jobs "
  listening=false
  for _ in $(seq 1 30); do
    if docker logs "$runner" 2>&1 | grep -q 'Listening for Jobs'; then
      listening=true
      echo " yes."
      break
    fi
    echo -n "."
    sleep 3
  done
  if [ "$listening" != true ]; then
    echo ""
    echo -e "${YELLOW}Your runner is not listening yet. Its log:${NC}"
    docker logs --tail 15 "$runner" 2>&1 | sed 's/^/    /'
    echo "A registration error usually means RUNNER_TOKEN in .env expired (one hour)."
    echo "Ask for a fresh token, put it in .env, then:"
    echo "    docker compose --profile test up -d --force-recreate test-runner"
  fi
fi

# ---- summary ----------------------------------------------------------------

echo ""
echo -e "${GREEN}Ready.${NC}"
echo "  gateway    $(gateway_url local)   admin / password"
echo "  demo       $(gateway_url local)/data/perspective/client/oatmakers/"
echo "  postgres   localhost:$(setting POSTGRES_PORT 5432)          ignition / $(cat local-development/secrets/POSTGRES_PASSWORD)"
if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  echo "  test gw    $(gateway_url test)   admin / password   (your deploy target)"
  echo "  runner     docker logs $(stack_name)-test-runner-$LAB_USER_VALUE   (look for 'Listening for Jobs')"
fi
echo ""
echo "git status should be clean now. If the identity files ever show up dirty"
echo "again, re-run this script (CI blocks them from merging anyway)."
