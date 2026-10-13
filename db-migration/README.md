# db-migration/migrate/

golang-migrate pairs for the database the gateway's connections use
(`ignition`). They run BEFORE anything ships: locally with
`scripts/migrate.sh up` (setup.sh does it for you), on your Part 0 test
gateway by your test workflow, and on production by the Deploy workflow. A
failed migration stops the deploy.

Rules (lab 06):

- **Always pairs.** `NNNNNN_name.up.sql` creates, `NNNNNN_name.down.sql`
  undoes it. CI fails the PR if one of the two is missing.
- Numbers are the ledger order: take the next free number, exactly like the
  release tags.
- The applied position lives in the database's `schema_migrations` table,
  the same table in every environment.

`000001` to `000006` build the demo's simulation schema `oat_demo`.
