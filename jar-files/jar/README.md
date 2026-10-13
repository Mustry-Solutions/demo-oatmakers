# jar-files/jar/

Library JARs the deploy copies into the gateway's `lib/core/gateway/` (loaded
at boot: the deploy restarts the gateway when one changes). Pin exact
versions and record where every JAR came from:

| JAR | Source | Checksum (sha256) |
|---|---|---|

No library JARs ship at the moment.

The deploy owns the JARs it copied in: delete one here, and the next release
removes it from the gateway again (one restart). JARs the image brings itself
are never touched.

Pick a library the gateway does not already have: the Ignition image bundles
commons-lang3, commons-text, commons-math3, guava and friends under
`lib/core/common/`, so importing those succeeds without the pipeline shipping
anything. Check with:

```bash
docker exec oatmakers-gateway sh -c 'ls /usr/local/bin/ignition/lib/core/*/' | grep -i <name>
```
