#!/usr/bin/env bash
# Make production's database login for the gateway match the repository.
#
# Every database connection in services/config logs in as the plain username
# `ignition` (Ignition cannot reference a secret for the username) with the
# referenced secret POSTGRES_PASSWORD from the `environment` file provider.
# Locally both come from local-development/secrets. On production the
# database's own password file is mounted into the gateway as
# /run/secrets/POSTGRES_PASSWORD, and this script makes sure the role
# `ignition` exists with exactly that password. It runs inside the database
# container with the container's own secret files, so no credential is passed
# in from outside.
#
# For the migrations that follow, it exports POSTGRES_USERNAME=ignition and the
# (masked) password to $GITHUB_ENV.
set -euo pipefail
container="${POSTGRES_CONTAINER:-cicd-capstone-postgres}"
database="${POSTGRES_DB:-ignition}"

docker exec -i -e DB="$database" "$container" sh -c '
  set -eu
  admin="${POSTGRES_USER:-}"
  if [ -n "${POSTGRES_USER_FILE:-}" ]; then admin="$(cat "$POSTGRES_USER_FILE")"; fi
  password="${POSTGRES_PASSWORD:-}"
  if [ -n "${POSTGRES_PASSWORD_FILE:-}" ]; then password="$(cat "$POSTGRES_PASSWORD_FILE")"; fi
  test -n "$admin" && test -n "$password" || { echo "Database credentials are missing in the container." >&2; exit 1; }
  # Superuser like the local POSTGRES_USER: the TimescaleDB Historian creates
  # its extension, and the demo owns its schema.
  psql -U "$admin" -d "$DB" -X -q -v ON_ERROR_STOP=1 -v pw="$password" -f - >/dev/null
  # TCP login verifies the password, unlike the trusted local socket.
  PGPASSWORD="$password" psql -h 127.0.0.1 -U ignition -d "$DB" -X -tA -v ON_ERROR_STOP=1 -c "SELECT 1" >/dev/null
' <<'SQL'
SELECT 'CREATE ROLE ignition LOGIN SUPERUSER'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ignition') \gexec
SELECT format('ALTER ROLE ignition LOGIN SUPERUSER PASSWORD %L', :'pw') \gexec
SQL
echo "Database role 'ignition' matches the server's password."

if [ -n "${GITHUB_ENV:-}" ]; then
  password="$(docker exec "$container" sh -c 'if [ -n "${POSTGRES_PASSWORD_FILE:-}" ]; then cat "$POSTGRES_PASSWORD_FILE"; else printf "%s" "${POSTGRES_PASSWORD:-}"; fi')"
  case "$password" in *$'\n'*|*$'\r'*) echo 'Multiline database passwords are not supported.' >&2; exit 1;; esac
  masked="${password//%/%25}"
  printf '::add-mask::%s\n' "$masked"
  umask 077
  printf 'POSTGRES_USERNAME=ignition\nPOSTGRES_PASSWORD=%s\n' "$password" >> "$GITHUB_ENV"
fi
