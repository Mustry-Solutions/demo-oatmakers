# Oatmakers customer demo

Open https://cloud.mustrysolutions.com/data/perspective/client/oatmakers/ or launch **Oatmakers | Connected factory demo** from the Perspective launcher. Reload an existing session after a release.

All measurements and orders are simulated. Writes are confined to the `oat_demo` database schema and the `[default]OatmakersDemo` and `[default]OatMill` memory tags. The SCADA faceplates write operator settings (mode, Manual commands, valve position, alarm limits) to the simulated `OatMill` tags; no screen controls real equipment or changes customer records.

## Screens

| Route | Purpose |
|---|---|
| `/` | One-second throughput, current shift output, line conditions and alerts |
| `/scada` | Plant overview: every process area as a live tile; click a tile to open its SCADA screen |
| `/scada/intake`, `/scada/cleaning`, `/scada/dehulling`, `/scada/kiln`, `/scada/flaking`, `/scada/cutting`, `/scada/milling`, `/scada/packing`, `/scada/utilities` | Process area drawings with live instruments, motors, silo levels, trends and read-only detail popups |
| `/production` | Mustry Resource Timeline with shift, day, hour and week navigation; click a batch for details |
| `/performance` | Mustry Date Time Range Picker controlling historical charts and aggregate metrics |
| `/quality` | Mustry Data Grid for batches in the selected dates, with measurement and inspection details |
| `/operator` | Completed-batch output entry alongside an independently scrolling Mustry Data Grid |
| `/demo/health` | Telemetry age, retained history and continuity status |

Legacy `/process`, `/oee` and `/demo/input-fields` links open SCADA, Performance and Batch output. The course observatory remains at `/observatory`. The component library is removed from the customer navigation and routes.

## Demonstration walkthrough

1. Watch the factory throughput and line readings change every second.
2. Open SCADA in the menu and drill down to a process group and area, or open the plant overview and click a tile. Click a blue stream link to follow the product to the next area, and click an instrument, motor, valve or silo for its faceplate: change its mode or alarm limits there and watch the drawing follow.
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
# pip install iglint==0.1.0
iglint check
python3 tests/demo/test_database.py
python3 tests/test_deploy_payload.py
```

Database tests use a disposable `_test` database. They check real SQL, exact history ranges, line filters, moving fine telemetry, quantity reconciliation, retention, idempotency and recovery after weeks or months offline. The payload test runs the release steps of the Deploy workflow against a throwaway repository. `build_views.py` regenerates the Perspective resources and `tools/demo/check_generated.py` verifies they are committed. The SCADA drawings are generated by `build_scada.py`; rebuilding requires no external project checkout.

## Cloud deployment and recovery

Release through an immutable project tag and the `release.yaml` pin; the Deploy workflow applies it on the production runner. Migrations run first, recorded in `schema_migrations` like every other environment. The demo's database connection logs in as `ignition` with the referenced secret `POSTGRES_PASSWORD` from the `environment` file provider; on production the server stack mounts the database password at `/run/secrets/POSTGRES_PASSWORD` and the workflow keeps the `ignition` role aligned with it.

Projects and gateway configuration are replaced as a whole and loaded through the scan API, except what the gateway owns: its name, internal users, API token, keys and tag values. A changed module manifest, module binary or JAR restarts the gateway once; project-only changes use hot scans.

After a deploy the workflow verifies that the one-second heartbeat advances, retained history is populated and all seven public routes respond. A failure fails the run; nothing is restored automatically. Roll back by reverting the release PR.

The Deploy workflow's readiness job runs every six hours (and on demand with `readiness_only`). It reads database health directly and checks public routes, so it does not require a Web Dev license. The optional `/system/webdev/oatmakers/api/demo-health` endpoint also returns health where Web Dev is available. An HTTP route check alone does not validate rendering; release review additionally exercises the real screens in a browser.

For failures, inspect Actions, Demo health, database connection `OatmakersDemo`, secret provider `environment` and gateway logger `Oatmakers.Demo`. Restoring the connection lets the timer catch up automatically. The server's nightly gateway and database backups are managed by the server stack.

## Process SCADA

SCADA follows the oat from truck to pallet: intake and raw oat silos, cleaning,
dehulling, kilning, the three production lines (flaking, cutting, milling),
packing, and the steam and compressed air utilities. The sidebar menu is a
Perspective Menu Tree: SCADA drills down into its process groups and areas, and
the current page is highlighted.

Each area is a fixed 1740 by 910 drawing under `Pages/Scada/Drawings/`, embedded
in Mustry Pan & Zoom by its page `Pages/Scada/<Area>` (the overview is
`Pages/Scada/Overview`). The reusable SCADA views are templates under
`Templates/Hmi/`:

| Template | Parameters |
|---|---|
| `Instrument` | `tagPath` of an `AnalogInput`, optional `colour` for controllers |
| `Device/Motor`, `Fan`, `RotaryValve`, `Pump` | `tagPath` of a `Motor` |
| `Device/ControlValve`, `ShutoffValve` | `tagPath` of a `Valve` |
| `Silo` | `tagPath` of a `Silo`, `height` |
| `AreaState`, `Tile` | `tagPath` of a `ProcessArea` (`.../<Area>/Area`) |
| `Trend` | `tagPath` of an `AnalogInput` or `Silo` |
| `Stream` | `text`, `target` route, `width` |
| `Equipment/*` (27 outlines) | `tag`, `title`, `width`, `height`, `labelX`, `labelY` |

A live template only needs the full instance path, for example
`[default]OatMill/Flaking/TIC501`: it reads value, unit, decimals, kind and
alarm state from the instance's members through indirect tag bindings, and its
tag label is the last path element. The equipment outlines carry no tags.

All graphics are Perspective drawings (`ia.shapes.svg`), never images: the
piping is one drawing per area, live state binds to drawing element properties
(fill paint, path, width, viewBox), and every text is a Label component. The
session property `showLabels` (default on) shows or hides all labels; the Labels
switch in the header dock (`Docks/Header`, on every page next to the breadcrumb)
toggles it. Blue stream links navigate to the area
that supplies or receives the product; grey links leave the plant. The page
header has previous and next buttons in process order.

### Faceplates

Clicking an instrument, motor, valve or silo opens its faceplate
`Popups/Faceplates/<UDT>` with the instance path. A faceplate shows the name,
description and full tag path, the live value with status, the operator
settings, the Manual commands, and a chart with time and value axes over a 1 h,
8 h or 24 h preset. Settings are staged: edit them, then press Write to send them
to the tag (Cancel takes the live values back). Manual commands act immediately
and are only enabled in Manual:

| Faceplate | Writes | Chart |
|---|---|---|
| `AnalogInput` | `LowLimit`, `HighLimit` | measured value and alarm limits |
| `Motor` | `Mode` (Auto, Manual, Off); Start and Stop in Manual (`ManualRun`) | motor current |
| `Valve` | `Mode`, `PositionSP` (control valves in Manual); Open and Close in Manual (`ManualOpen`) | valve position |
| `Silo` | `LowLimit`, `HighLimit` | level and limits |

The chart uses the recorded line history for the line measurements and the
same deterministic model that drives the tags elsewhere. Written settings act
at once: Off stops a drive or closes a valve, Manual hands it to the Start/Stop
or Open/Close commands whatever the process state, and a limit change switches
the alarm. Switching to Manual is bumpless: the Manual command starts from the
current running or open state.

### Tags

`[default]OatMill/<Area>` holds one UDT instance per instrument, drive, valve
and silo on the drawing, plus an `Area` instance with the area state. UDT
parameters are exposed as expression members, so templates and faceplates can
read them from the instance path:

| UDT | Process members | Settings (written from faceplates) | Parameter members |
|---|---|---|---|
| `OatMill/AnalogInput` | `PV`, `Alarm` | `LowLimit`, `HighLimit` | `Kind`, `Description`, `Unit`, `Decimals` |
| `OatMill/Motor` | `Running`, `Fault`, `Current` | `Mode`, `ManualRun` | `Description`, `Duty`, `RatedCurrent` |
| `OatMill/Valve` | `Open`, `Position` | `Mode`, `ManualOpen`, `PositionSP` | `Description` |
| `OatMill/Silo` | `Level`, `Content`, `Alarm` | `LowLimit`, `HighLimit` | `Description`, `Product`, `Capacity` |
| `OatMill/ProcessArea` | `State`, `Running`, `LastUpdate` | | `Title` |

The `DemoContinuity` gateway timer writes the simulation into the process
members every second. It finds the instances by browsing `[default]OatMill`,
reads which model signal each carries from its `Signal` parameter, and respects
the written `Mode`, Manual commands and `PositionSP`. The line areas take throughput,
temperature, moisture, steam pressure and power from the recorded line
telemetry and follow the line state: a stopped line stops its drives and closes
its valves (in Auto). A plain tag property does not substitute UDT parameters,
so `engUnit` and `documentation` are bound to them explicitly.

`tools/demo/build_scada.py` generates the drawings, templates and faceplates
and, through `tools/demo/build_tags.py`, the UDT definitions and instances.
Change them, run `build_views.py` and commit the result. Initial alarm limits
are instance values of the `LowLimit` and `HighLimit` members; a gateway only
applies a changed initial value when it creates the tag.

Performance initializes its picker outputs and embedded range parameters before
bindings evaluate. Null or pending ranges return a valid empty chart. Error
overlays remain enabled. `tests/demo/test_view_startup.py` verifies startup states
and the transition to a valid history query.

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
