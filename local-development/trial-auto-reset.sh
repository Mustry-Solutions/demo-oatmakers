#!/usr/bin/env bash
#
# Keep an unlicensed local gateway out of the "Trial Expired" state.
#
# An unlicensed gateway runs on a two-hour trial. When it lapses, application
# endpoints answer `HTTP 402 Trial Expired` and Perspective sessions stop until
# someone presses Reset Trial. The gateway only accepts that reset once the trial
# has genuinely expired (it answers 403 before), so the outage cannot be avoided,
# only shortened: this script starts a background watcher that sleeps until the
# trial is about to run out, then polls every TRIAL_AUTO_RESET_POLL_SECONDS and
# issues the reset the moment the gateway reports it expired. The resulting gap is
# typically under two seconds. scripts/reset-trial.sh does the same reset by hand.
#
# docker-compose.yaml runs this from the gateways' entrypoint, right before the
# stock docker-entrypoint.sh. Enabled by TRIAL_AUTO_RESET:
#   auto (default)  on when the config mode is tst or stg, off otherwise
#   true / false    force it on or off
# The config mode comes from IGNITION_CONFIG_MODE. The local gateways run without
# one, so docker-compose.yaml sets TRIAL_AUTO_RESET=true for them.
# A licensed gateway is never touched: the watcher only acts on licenseMode Trial.
#
# The watcher authenticates with an api-token it mints itself: a random secret per
# boot, whose hash is written into the live config before the gateway starts. Every
# boot overwrites it, so the secret never outlives the container start, and no
# secret is committed or has to be provisioned. The resource lands under
# api-token/, which .gitignore keeps out of git for the bind-mounted local gateway.
#
# The watcher runs detached from the startup sequence, so a failure in it never
# blocks the gateway start; it logs and retries instead.

set -euo pipefail

log() {
    printf '[trial-auto-reset] %s\n' "$*"
}

mode="${IGNITION_CONFIG_MODE:-}"
case "${TRIAL_AUTO_RESET:-auto}" in
    true) ;;
    false)
        log "disabled by TRIAL_AUTO_RESET=false"
        exit 0
        ;;
    auto)
        case "${mode}" in
            tst|stg) ;;
            *)
                log "not started: config mode '${mode:-unknown}' is not tst or stg (set TRIAL_AUTO_RESET=true to force)"
                exit 0
                ;;
        esac
        ;;
    *)
        log "not started: unsupported TRIAL_AUTO_RESET='${TRIAL_AUTO_RESET}' (use auto, true or false)"
        exit 0
        ;;
esac

readonly ignition_install_location="${IGNITION_INSTALL_LOCATION:-/usr/local/bin/ignition}"
readonly token_dir="${ignition_install_location}/data/config/resources/core/ignition/api-token/trial-auto-reset"
readonly gateway="http://localhost:${GATEWAY_HTTP_PORT:-8088}"
readonly poll_seconds="${TRIAL_AUTO_RESET_POLL_SECONDS:-0.2}"
# Start polling this long before the reported expiry. The last sleep is computed from
# a fresh reading, so only rounding of trialSecondsLeft and request latency need
# absorbing; a short lead keeps the fast polling to a few seconds per trial period.
readonly lead_seconds=3
# Re-read the trial state at least this often while waiting, so a gateway restart
# or a manual reset never leaves the watcher sleeping on a stale countdown.
readonly max_sleep_seconds=300

base64url() {
    base64 -w0 | tr '+/' '-_' | tr -d '='
}

# Ignition stores base64url(sha256(secret bytes)) and expects "<name>:<base64url(secret)>".
# The image has no openssl, so the hex digest from sha256sum is decoded back to bytes.
mint_token() {
    local secret_file
    secret_file="$(mktemp)"
    head -c 32 /dev/urandom > "${secret_file}"
    token="trial-auto-reset:$(base64url < "${secret_file}")"
    token_hash="$(sha256sum < "${secret_file}" | cut -c1-64 | tr 'a-f' 'A-F' | basenc --base16 -d | base64url)"
    rm -f "${secret_file}"
}

# The token gets the Authenticated/APIKEY level, like the scan-API key from
# scripts/generate-api-key.sh: the committed security-properties grants write access
# to it. A gateway still on the stock policy (a test gateway before its first deploy)
# answers 403 until that policy arrives.
write_token_resource() {
    mkdir -p "${token_dir}"
    jq -n --arg hash "${token_hash}" --argjson timestamp "$(date +%s%3N)" '{
        profile: {
            secureChannelRequired: false,
            securityLevels: [{
                name: "Authenticated",
                description: "Represents a user who has been authenticated by the system.",
                children: [{name: "APIKEY", children: []}]
            }],
            timestamp: $timestamp,
            type: "basic-token"
        },
        settings: {tokenHash: $hash}
    }' > "${token_dir}/config.json"
    jq -n --arg uuid "$(cat /proc/sys/kernel/random/uuid)" --arg now "$(date -u +%FT%TZ)" '{
        scope: "A",
        description: "Minted at boot by local-development/trial-auto-reset.sh",
        version: 1,
        restricted: false,
        overridable: true,
        files: ["config.json"],
        attributes: {
            lastModification: {actor: "trial-auto-reset", timestamp: $now},
            uuid: $uuid,
            enabled: true
        }
    }' > "${token_dir}/resource.json"
}

# Prints "<licenseMode> <expired> <trialSecondsLeft>", or fails when the gateway is
# unreachable (still starting, restarting) or answers something unexpected. Reading
# the trial state needs no authentication; only the reset does.
read_trial() {
    curl -fsS -m 5 "${gateway}/data/api/v1/trial" 2>/dev/null \
        | jq -er '"\(.licenseMode) \(.expired) \(.trialSecondsLeft | floor)"' 2>/dev/null
}

reset_trial() {
    curl -sS -m 5 -o /dev/null -w '%{http_code}' \
        -X POST -H "X-Ignition-API-Token: ${token}" "${gateway}/data/api/v1/trial" 2>/dev/null
}

now_ms() {
    date +%s%3N
}

watch_trial() {
    local state license expired seconds_left status expired_since_ms=""
    local unreachable_logged=false failed_status="" failed_attempts=0

    log "watching ${gateway} (config mode '${mode:-unknown}', poll ${poll_seconds}s)"
    while true; do
        if ! state="$(read_trial)"; then
            if [[ "${unreachable_logged}" == false ]]; then
                log "trial state unavailable; retrying (gateway starting or restarting)"
                unreachable_logged=true
            fi
            # Stay fast while the trial is known to be expired, so a hiccup right at
            # the reset does not stretch the outage.
            if [[ -n "${expired_since_ms}" ]]; then sleep "${poll_seconds}"; else sleep 5; fi
            continue
        fi
        unreachable_logged=false
        read -r license expired seconds_left <<<"${state}"

        if [[ "${license}" != "Trial" ]]; then
            sleep "${max_sleep_seconds}"
            continue
        fi

        if [[ "${expired}" == "true" ]]; then
            [[ -n "${expired_since_ms}" ]] || expired_since_ms="$(now_ms)"
            status="$(reset_trial)"
            if [[ "${status}" == "200" ]]; then
                log "trial reset $(( $(now_ms) - expired_since_ms )) ms after expiry was detected"
                expired_since_ms=""
                failed_status=""
                failed_attempts=0
                continue
            fi
            # A 403 on an expired trial means the token lacks permission. Ignition does
            # not apply api-token permissions on a gateway's very first boot, so that
            # case only clears at the next restart: log once and slow down.
            if [[ "${status}" != "${failed_status}" ]]; then
                log "reset returned HTTP ${status:-none}; retrying"
                failed_status="${status}"
            fi
            failed_attempts=$(( failed_attempts + 1 ))
            if (( failed_attempts < 25 )); then sleep "${poll_seconds}"; else sleep 5; fi
            continue
        fi

        expired_since_ms=""
        failed_status=""
        failed_attempts=0
        if (( seconds_left > lead_seconds )); then
            sleep "$(( seconds_left - lead_seconds < max_sleep_seconds ? seconds_left - lead_seconds : max_sleep_seconds ))"
        else
            sleep "${poll_seconds}"
        fi
    done
}

# On a never-booted data volume the gateway creates the core resource collection
# itself and faults when that directory already has content, so leave it alone. The
# api-token would not be honored on that first boot anyway; the next start mints it.
if [[ ! -f "${ignition_install_location}/data/config/resources/core/config-mode.json" ]]; then
    log "not started: first boot of this data volume, the watcher starts from the next restart"
    exit 0
fi

token=""
token_hash=""
mint_token
write_token_resource
log "api-token written to ${token_dir#"${ignition_install_location}/data/"}"

# Detach from the startup sequence: the entrypoint execs the gateway right after
# this script, and the watcher keeps running alongside it.
set +e
watch_trial </dev/null &
disown
