# OatMakers Demo

The Oatmakers demo: an Ignition 8.3 application for a fictional oat factory,
running live at https://cloud.mustrysolutions.com. It is also the shared
production repo for Lab 07 of the Mustry Academy course
[CI/CD for Ignition](https://github.com/Mustry-Academy/cicd-for-ignition).

## Repo layout

```
release.yaml                 what runs on production, right now (the ONLY deploy trigger)
projects/oatmakers/          the demo application (shared project)
projects/<name>/             one project per Lab 07 contributor
services/config/             gateway configuration export
services/modules.json        module manifest (trust values per module)
third-party-modules/         .modl files the pipeline installs (Mustry UI, TimescaleDB Historian)
jar-files/jar/               library JARs, loaded from the gateway's JAR directory
db-migration/migrate/        golang-migrate up/down pairs, run before anything ships
local-development/secrets/   local stand-ins for the referenced database secrets
scripts/                     setup, teardown, validate, migrate, scan, reset-trial, API keys
tools/demo/  tests/          demo view generator, readiness checks and tests
docker-compose.yaml          local gateway + database (+ the Part 0 test stack)
ops/compose.runner.yml       the production runner definition
.github/workflows/           ci.yml (PR checks) · deploy.yml (release.yaml -> production)
                             · test-example.yml.template (Part 0, copy per person)
```

## Quick start

```bash
./scripts/setup.sh       # database + migrations + gateway, idempotent
./scripts/validate.sh    # local mirror of CI, green before you open a PR
```

| Service | URL | Login |
|---|---|---|
| local gateway | http://localhost:8088 | `admin` / `password`, bind-mounted from `./projects/` and `./services/config/` |
| the demo | http://localhost:8088/data/perspective/client/oatmakers/ | |
| local database | localhost:5432 | `ignition` / `oatmakers-local-pw`, database `ignition` |
| production | https://cloud.mustrysolutions.com | deploys land here through `release.yaml` only |

Startup applies the database migrations and runs the continuity timer, with
90 days of simulated history and six hours of live telemetry. Gateway and
database state live in Docker volumes. Ports already in use? Set
`GATEWAY_PORT`, `TEST_GATEWAY_PORT` or `POSTGRES_PORT` in `.env`.

The local gateway bind-mounts the repo: a save in the Designer lands in your
working tree, so `git status` is your export step. After editing files by
hand, `scripts/scan.sh` reloads projects and config without a restart. A JAR
you put in `jar-files/jar/` loads after `docker compose restart gateway`.
`scripts/migrate.sh up` applies new migration pairs. The gateway runs in
two-hour trial mode; `scripts/reset-trial.sh` resets it. Stop everything with
`scripts/teardown.sh` (add `--volumes` for a factory reset).

## How a change reaches production

1. Change it locally, open a PR. `CI OK` must be green and a reviewer
   approves; merging deploys nothing.
2. Tag the merged commit: `git tag <project>@vX.Y.Z && git push origin <project>@vX.Y.Z`
   (the next free version: `git fetch --tags && git tag -l '<project>@*'`).
3. Pin the tag in `release.yaml` in a second PR. CI refuses a pin whose tag
   does not exist or points at a commit that is not on `main`.
4. Merging that PR runs `.github/workflows/deploy.yml` on the production
   runner: every pinned project from its own tag, plus the gateway config,
   module manifest, third-party modules, JARs and migrations from the
   `oatmakers` tag. Projects and config reload hot; a changed module or JAR
   restarts the gateway once. Modules and JARs live in volumes on the
   gateway, so they survive a container recreate. The demo's readiness check
   must pass.

Roll back by reverting the release PR. The Deploy workflow also has a manual
`readiness_only` run and checks the running demo every six hours. A manual
deploy only runs from `main`.

The gateway's own identity never ships and is never wiped: its name
(system-properties), internal users and identity provider, the scan-API
token, its secrets keys and tag values.

## Lab 07 Part 0: your personal test gateway

Put `LAB_USER=<yourname>` and the `RUNNER_TOKEN` from the chat in `.env`, run
`./scripts/setup.sh`, and it also starts a test gateway on
http://localhost:8090 with its own database (`oatmakers-test-postgres`, no
host port) and your own runner labelled `<yourname>-local`. Check the runner
with `docker logs oatmakers-test-runner-<yourname>` ("Listening for Jobs").
Only your test workflow migrates that database: what you try locally with
`scripts/migrate.sh` stays in your local one (`scripts/migrate.sh --test ...`
reaches the test one when you need to repair it).
Copy `.github/workflows/test-example.yml.template` to
`.github/workflows/test-<yourname>.yml`, set
`runs-on: [self-hosted, <yourname>-local]`, and every push to `main` deploys
`main` to your test gateway. Once that file is on `main`,
`gh workflow run test-<yourname>.yml --ref <branch>` deploys a branch to your
test gateway before you merge it.

To rotate your scan-API key, empty `IGNITION_API_KEY` in `.env` and run
`./scripts/setup.sh` again: it generates a new key, puts it on both gateways
and your runner, restarts each gateway that still has the old one, and checks
that the new key works.

## Tests

`ci.yml` runs on every pull request. The demo checks also run locally;
the database test needs a disposable Postgres on `localhost:5432`:

```bash
python3 tools/demo/check_generated.py   # generated views match tools/demo/build_views.py
python3 tools/demo/validate.py
python3 tests/demo/test_view_startup.py
python3 tests/demo/test_database.py
python3 tests/test_deploy_payload.py    # needs PyYAML
```

The views under `views/Demo/`, the page routes, session props and the
stylesheet are generated: change `tools/demo/build_views.py`, run it, and
commit the result.

## Licence

[Apache 2.0](./LICENSE). © 2026 Mustry Solutions BV.
