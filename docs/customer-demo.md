# Oatmakers customer demo

Open https://cloud.mustrysolutions.com/data/perspective/client/oatmakers/ or launch **Oatmakers | Connected factory demo** from the Perspective launcher. Reload an existing session after a release.

All measurements and orders are simulated. Writes are confined to the `oat_demo` database schema and `[default]OatmakersDemo` memory tags. No screen controls equipment or changes customer records.

## Screens

| Route | Purpose |
|---|---|
| `/` | One-second throughput, current shift output, line conditions and alerts |
| `/scada` | Separator A process drawing with live instruments, embedded vessel trends and read-only detail popups |
| `/production` | Mustry Resource Timeline with shift, day, hour and week navigation; click a batch for details |
| `/performance` | Mustry Date Time Range Picker controlling historical charts and aggregate metrics |
| `/quality` | Mustry Data Grid for batches in the selected dates, with measurement and inspection details |
| `/operator` | Completed-batch output entry alongside an independently scrolling Mustry Data Grid |
| `/demo/health` | Telemetry age, retained history and continuity status |

Legacy `/process`, `/oee` and `/demo/input-fields` links open SCADA, Performance and Batch output. The course observatory remains at `/observatory`. The component library is removed from the customer navigation and routes.

## Demonstration walkthrough

1. Watch the factory throughput and line readings change every second.
2. Open SCADA. Inspect the complete Separator A process and its vessel trends, then click an instrument for its live detail popup.
3. On Performance, choose a live preset or exact calendar dates and times. The selected range controls the database query. Manual selections stop following the clock.
4. Open Production planning, change between shift and week scales, and inspect a batch.
5. In Quality, choose older dates, select a batch, inspect its measurements and record a demo inspection.
6. In Batch output, select a completed batch and record its actual output and bag count. The record appears in the grid and remains after reloading. The form has no internal scrollbar.

## Data lifecycle

The dedicated gateway timer runs every second even without a browser. It records deterministic, changing measurements for three lines and writes their latest values to the OatMakers memory tags. Tag-history popups query the same recorded source. A disconnected source shows unavailable readings rather than invented browser values.

Fine telemetry is retained for six hours. Minute history, orders and inspections are retained for the shorter of 90 days and three calendar months. First deployment seeds the retained history. Watermarks fill gaps after downtime, bounded by those retention windows. Database advisory locks prevent overlapping generators and repeated timestamps insert nothing.

One-second production quantities sum to their minute totals. Charts use fine data for recent ranges and minute data for older ranges, with at most approximately 900 plotted points. Line filters and explicit start/end timestamps are applied in SQL. Throughput and power are normalized by the represented duration. The overview emphasizes current operation; slower aggregate efficiency metrics are on Performance.

Batch output and quality are derived from the line-specific recorded production plan. A peak moisture excursion can require review despite an acceptable average. Requests and inspections are persistent demo records; repeated submission IDs cannot create duplicates.

## Mustry UI module

The pinned signed `third-party-modules/Mustry_UI-0.5.2.modl` is built from the source commit and Actions run recorded in `third-party-modules/README.md`, together with its sha256. The module manifest marks it as free, so it does not rely on a trial license. `services/modules.json` registers it with its certificate fingerprint and licence hash.

Screens use the module's Date Time Range Picker, Resource Timeline, Data Grid. The module has no chart renderer; the shared history view pairs its range picker with a styled native Perspective XY chart. The picker output, not a separate preset dropdown, defines the queried range.

## Local development

`docker-compose.yaml` runs Ignition 8.3.8 at http://localhost:8088 (`admin` / `password`) and TimescaleDB on PostgreSQL 17 at `localhost:5432`. Run `scripts/setup.sh`: it starts the database, applies the migrations, starts the gateway with the repository bind-mounted and the modules from `third-party-modules/`, and fixes the first-boot identity. Set `GATEWAY_PORT` or `POSTGRES_PORT` in `.env` when those ports are taken.

After changing resources:

```sh
scripts/scan.sh
scripts/validate.sh
# pip install iglint==0.1.0 --find-links https://github.com/Mustry-Solutions/iglint/releases/expanded_assets/v0.1.0
iglint check
python3 tests/demo/test_database.py
python3 tests/test_deploy_payload.py
```

Database tests use a disposable `_test` database. They check real SQL, exact history ranges, line filters, moving fine telemetry, quantity reconciliation, retention, idempotency and recovery after weeks or months offline. The payload test runs the release steps of the Deploy workflow against a throwaway repository. `build_views.py` regenerates the Perspective resources and `tools/demo/check_generated.py` verifies they are committed. The separator geometry is generated by `build_separator.py`; rebuilding requires no external project checkout.

## Cloud deployment and recovery

Release through an immutable project tag and the `release.yaml` pin; the Deploy workflow applies it on the production runner. Migrations run first, recorded in `schema_migrations` like every other environment. The demo's database connection logs in as `ignition` with the referenced secret `POSTGRES_PASSWORD` from the `environment` file provider; on production the server stack mounts the database password at `/run/secrets/POSTGRES_PASSWORD` and the workflow keeps the `ignition` role aligned with it.

Projects and gateway configuration are replaced as a whole and loaded through the scan API, except what the gateway owns: its name, internal users, API token, keys and tag values. A changed module manifest, module binary or JAR restarts the gateway once; project-only changes use hot scans.

After a deploy the workflow verifies that the one-second heartbeat advances, retained history is populated and all seven public routes respond. A failure fails the run; nothing is restored automatically. Roll back by reverting the release PR.

The Deploy workflow's readiness job runs every six hours (and on demand with `readiness_only`). It reads database health directly and checks public routes, so it does not require a Web Dev license. The optional `/system/webdev/oatmakers/api/demo-health` endpoint also returns health where Web Dev is available. An HTTP route check alone does not validate rendering; release review additionally exercises the real screens in a browser.

For failures, inspect Actions, Demo health, database connection `OatmakersDemo`, secret provider `environment` and gateway logger `Oatmakers.Demo`. Restoring the connection lets the timer catch up automatically. The server's nightly gateway and database backups are managed by the server stack.

## Separator reference screen

SCADA uses a complete Separator A process layout based on the supplied reference:
a horizontal vessel, connected inlet/export/drain piping, instrument badges,
valve and pump symbols, and three trends inside the vessel. The scene preserves
its 1740:910 aspect ratio. SCADA keeps the normal application sidebar, logo and page header. The separator
is one view inside the application, with no separate process navigation bar.

Instrument, device, stream, trend and detail elements are reusable embedded
Perspective views under `Demo/Separator/`. Readings and the one-hour trend are
from a deterministic, read-only separator simulation, separate from the
OatMakers production database. Instrument and connected-equipment clicks open a detail popup. No view writes
to plant controls.

Performance initializes its picker outputs and embedded range parameters before
bindings evaluate. Null or pending ranges return a valid empty chart. Error
overlays remain enabled. `tests/demo/test_view_startup.py` verifies startup states
and the transition to a valid history query.

Geometry uses a common design coordinate system for piping, instrument circles,
value badges, valve bodies and highlighted frames. Device flow ports share the
same axis as their connected pipes. Instrument leads stop at circle boundaries,
and pneumatic lines stop at the AS/I-P enclosures instead of crossing their text.

## Separator navigation

`Demo/Separator/Process` contains the complete diagram and its live bindings in
fixed 1740 by 910 coordinates. `Demo/SCADA` embeds it with Mustry Pan & Zoom.
Wheel zoom, drag-to-pan, zoom buttons, reset, fit and the minimap are enabled.
The sidebar and page header stay outside the zoom transform. The view and
module content are transparent on the same grey background.

## Recording completed-batch output

The Batch output page lists completed batches with recorded production history.
Product, line and completion time come from the selected batch. The operator
enters actual output in kg and a bag count; bulk output uses zero bags.

Migration 000006 stores these records in `oat_demo.batch_output`, separately from
planned orders and simulated telemetry. Database validation rejects unfinished
or unknown batches and invalid quantities. A batch can be recorded once;
retried submissions return the existing record instead of duplicating it.
The continuity timer prunes output records using the existing 90-day or
three-calendar-month retention window. Existing order records are preserved.
