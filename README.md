# OatMakers Demo

The Oatmakers demo: an Ignition 8.3 application for a fictional oat factory,
running live at https://cloud.mustrysolutions.com. It is also the shared
production repo for Lab 07 of the Mustry Academy course
[CI/CD for Ignition](https://github.com/Mustry-Academy/cicd-for-ignition).

Edit `projects/oatmakers/` for the application,
`services/ignition/config/` for gateway resources, and `db-migration/migrate/`
for the simulation database. The pinned Mustry UI module lives in
`services/ignition/third-party-modules/`.

## Quick start

```bash
./ops/setup.sh
```

Open http://localhost:8088/data/perspective/client/oatmakers/.
Startup applies the database migrations and runs the continuity timer, with
90 days of simulated history and six hours of live telemetry. Gateway and
database state are retained in Docker volumes.

## Hot reload

```bash
./ops/trigger-scan.sh
```

This reloads the project and configuration from this checkout. Project changes
do not need a gateway restart.

## CI/CD

Changes to the demo on `main` run the project and database tests, then deploy
this repository's commit to `cloud.mustrysolutions.com`. No application code
or release tags are fetched from another repository. Deployment backs up the
demo resources and verifies live simulation data and page routes, preserving
the shared gateway identity and other applications.

The Deploy Oatmakers workflow also has a manual `readiness_only` check and
checks the running cloud demo every six hours.

## Tests

Pull requests to `main` run `.github/workflows/demo-tests.yml` on a
GitHub-hosted runner. The same checks run locally against a Postgres on
`localhost:5432`:

```bash
python3 tools/demo/build_views.py && git diff --exit-code -- projects/oatmakers
python3 tools/demo/validate.py
python3 tests/demo/test_view_startup.py
python3 tests/demo/test_database.py
python3 tests/demo/test_deploy.py
python3 tests/test_deploy_payload.py
```

## Teardown

```bash
./ops/teardown.sh
```

Volumes and simulation data are retained by default.

## Licence

[Apache 2.0](./LICENSE). © 2026 Mustry Solutions BV.
