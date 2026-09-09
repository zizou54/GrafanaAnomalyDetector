# 1.5.1 release gate

Status: **LOCAL CODE/UI GATE PASSED; PACKAGE PUBLICATION CHECKS REQUIRED**.

## Fresh checks on 2026-09-09

- Linux/Python 3.12 deployed exporter: 79/79 backend tests pass.
- Strict six-model clear/hard quality gate: three consecutive recorded Linux
  runs pass, without threshold changes. Minimum throughput by run: 12,049,
  12,672 and 10,493 points/CPU-second. A preceding fresh run also passed.
- Earlier Linux failures remain valid historical observations. Three new passes
  demonstrate the repeated gate on this host, not a CPU-independent throughput SLA.
- First browser rerun: 20 pass, one failure waiting for a transient clipboard
  success toast on ClickHouse. Follow-up verifies actual clipboard labels/query
  after returning focus from the rule-builder popup. Follow-up: 21/21 PASS.
- Visual inspection additionally found unavailable percentages and confidence
  duplicated as data quality. Both display issues are fixed; final post-fix UI
  rerun is 21/21 PASS, without skipped tests.
- Jest 45/45; production webpack/typecheck PASS; TS/Python 48,201 points PASS.
- Fresh read-only live audit 13/13 PASS, including six advancing saved routes.
- Version-matched E2E guide, three fresh 1920x1440 light-theme screenshots and
  21-page illustrated PDF rebuilt and visually reviewed.
- Packaging now rejects uncommitted package inputs and requires version-matched docs.

Evidence retained locally under output/release-*.log; logs and runtime secrets
are not distribution assets. A failed first run is not removed by a retry.

## Earlier verified scope

36/36 backend source-to-target routes with finite, fresh healthy data readback;
six live sources / 4,023 points captured TS/Python parity; five sink recoveries;
21/21 earlier browser suite. These are distinct checks, not a claim that all
36 live browser-to-sink timestamp pairs were intercepted and compared.

## Deployment acceptance outside this local gate

Real notification firing/resolved delivery, corporate HTTPS LB and authorization,
24-hour target-host soak, and labeled field-data acceptance remain required.
The earlier extra-36-route cycle took 13.702 seconds against a 5-second configured
interval. Benchmark CPU throughput excludes source/sink I/O and does not remove
that capacity limit. Never claim zero false positives or unlimited 7/24 capacity.

Release packaging must additionally pass extracted Python 3.9 import/config,
manifest, checksum, matched commit and secret/runtime exclusion checks before
publishing. Historical v1.5.0 and v1.5.0-r1 assets must remain unchanged.
