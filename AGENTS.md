This repository is the master source for the Oatmakers demo at cloud.mustrysolutions.com.

- The application lives in `projects/oatmakers/`, gateway resources in
  `services/ignition/config/`, simulation migrations in `db-migration/migrate/`.
- `ops/setup.sh` starts this code at http://localhost:8088 with the simulation,
  90 days of history and the pinned Mustry UI module.
- After changing project or config resources, run `ops/trigger-scan.sh`.
  Use hot reload; project changes do not need a gateway restart.
- `.github/workflows/deploy.yml` deploys committed demo changes on `main`
  to the shared gateway, after tests on GitHub-hosted runners.
- Deploy only Oatmakers-owned resources. Preserve the gateway identity,
  users, API tokens and unrelated applications.
- There is no lab repository or subtree dependency for development or deployment.
