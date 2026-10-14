# third-party-modules/

Third-party `.modl` files the pipeline installs on the gateway. A module lands
here in the same PR that registers it in
[`services/modules.json`](../services/modules.json) with its `certFingerprint`
and `licenseAgreementHash`; CI fails the PR when the two disagree. The deploy
ships the binaries, replaces the gateway's manifest, and restarts the gateway
only when something actually changed.

Locally the folder is mounted at `/third-party-modules` in the gateway, the
same path the manifest names on every gateway.

| Module | Version | Source | sha256 |
|---|---|---|---|
| `Mustry_UI-0.5.2.modl` (`com.mustrysolutions.perspective.components`) | 0.5.2, free | [Mustry-Solutions/mustry-perspective-component-module](https://github.com/Mustry-Solutions/mustry-perspective-component-module) commit `ee0713f`, build run 35343548742 | `47f0ff288cacba217c1b2de38d6ef2d3c9a2509d0ab34e373bb4cca3565ab24c` |
| `TimescaleDB-Historian.modl` (`com.mustry.historian.timescaledb`) | 0.9.10, licensed (runs in trial mode until a licence is activated) | Mustry Solutions | `bfe16e9d2c7d9f0bbbd27f5eeeca20c1d3e02d226513eda6ad926140ea4f3392` |
| `Project-Scan-Endpoint-1.0.0.modl` (`project-scan-endpoint`) | 1.0.0, free, MIT | [bw-design-group/ignition-project-scan-endpoint](https://github.com/bw-design-group/ignition-project-scan-endpoint/releases/tag/v1.0.0) release `v1.0.0` | `f0ffb9cf90f0dfb55647080399c4699a32d6ded0387e0142b7c1cb6212806722` |

The Project Scan Endpoint module is what Flint (the VS Code extension) calls
after you save a file: besides the gateway's own project scan, it tells open
Designers to reload the project. `flint.config.json` enables it for the local
gateway; `scripts/setup.sh` (through `scripts/generate-api-key.sh`) writes
the clone's API key into the gitignored token file it reads
(`.flint/tokens/local-api.json`).

The TimescaleDB Historian stores tag history in PostgreSQL through the
`timescaledb` extension (hypertables, compression, `time_bucket`). The local
database image and production's both ship the extension; the module creates
it on first use.

Where the two trust values of a new module come from is the lab 06 move: the
module and the gateway will tell you; this README won't.
