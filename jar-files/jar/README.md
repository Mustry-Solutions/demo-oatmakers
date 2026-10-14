# jar-files/jar/

Library JARs for the gateway's JAR directory,
`/usr/local/bin/ignition/user-lib/jars`, which the compose files add to the
gateway's classpath next to the image's own `lib/core/gateway/`. Your local
gateway bind-mounts this folder there: drop a JAR in and
`docker compose restart gateway`. Your test gateway and production keep the
JARs their deploy ships in a volume at that path, so a container recreate
does not lose them. JARs load at boot: the deploy restarts the gateway when
one changes. Pin exact versions and record where every JAR came from:

| JAR | Source | Checksum (sha256) |
|---|---|---|

No library JARs ship at the moment.

The deploy owns the JAR directory: delete a JAR here, and the next release
removes it from the gateway again (one restart). JARs the image brings itself
(`lib/core/`) are never touched.

Pick a library the gateway does not already have: the Ignition image bundles
commons-lang3, commons-text, commons-math3, guava and friends under
`lib/core/common/`, so importing those succeeds without the pipeline shipping
anything. Check with:

```bash
docker exec oatmakers-gateway sh -c 'ls /usr/local/bin/ignition/lib/core/*/' | grep -i <name>
```
