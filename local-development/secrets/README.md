# local-development/secrets: local stand-ins for the referenced secrets

These are NOT secrets. They are the documented defaults for the local compose
stack, committed on purpose so the same referenced-secret configuration works
on your machine and on production:

| File | Local value | On production |
|---|---|---|
| `POSTGRES_USERNAME` | `ignition` | not mounted (Ignition only accepts a referenced secret for the password; the username is the plain setting `ignition`) |
| `POSTGRES_PASSWORD` | `oatmakers-local-pw` | the production database password, mounted by the server stack |

`docker-compose.yaml` mounts this folder at `/run/secrets/` in the local
gateway, the test gateway and the local database. The gateway's file secret
provider `environment` reads `/run/secrets/POSTGRES_PASSWORD`, the same path it
reads on cloud.mustrysolutions.com, so a database connection that references
the secret `POSTGRES_PASSWORD` resolves locally and on production, each
against its own database. The database container reads the same files at its
first start (`POSTGRES_USER_FILE` / `POSTGRES_PASSWORD_FILE`), and
`scripts/migrate.sh` and the Part 0 test workflow use them for migrations.

Real secrets never go in this folder. Production values live on the
production server only.
