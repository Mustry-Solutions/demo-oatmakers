#!/usr/bin/env bash
# Package the committed cloud-demo resources from this repository.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
commit="${GITHUB_SHA:-HEAD}"
output="${1:?payload directory required}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
# Archive the commit, so uncommitted gateway state cannot enter a deployment.
git -C "$root" archive "$commit" -- \
  projects/oatmakers \
  services/ignition/config/resources/core/ignition/database-connection/OatmakersDemo \
  services/ignition/config/resources/core/ignition/secret-provider/DemoRuntime \
  db-migration/migrate services/ignition/third-party-modules tools/demo/mustry-ui-version.json | tar -x -C "$output"
printf 'Oatmakers payload from %s (%s)\n' "$commit" "$(git -C "$root" rev-parse --short "$commit")"
