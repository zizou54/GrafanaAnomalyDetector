# Anomaly Detector 1.5.1

Validation scope: [release gate](STATUS_v1.5.1.md).
Plugin and exporter must both be upgraded; API schema remains 3.

## Detection changes

- New opt-in Harmonic known-cycle model: 8-4096 post-bucketing samples per cycle,
  two complete cycles of warm-up, bounded reference and residual memory.
- Rolling z-score and MAD guard baseline updates during persistent deviations
  and account for correlated evidence without merging their mean/median identities.
- EWMA uses a guarded double-exponential reference with damped trend during an
  incident. Level shift shares that reference with its own evidence window and
  0.85 point weight. These are behavioral changes, not just faster implementations.
- Seasonal cycle periods >=8 use guarded phase peers and confidence-gated drift
  correction. Short-cycle and calendar refinements retain their separate paths.
- Window evidence must have current-point direction/deviation support. Recovery
  hysteresis, N-of-M, minimum activity and degraded-data decisions remain aligned
  between panel, canonical replay and streaming evaluation.
- Missing/non-finite source samples are not healthy zeros; repeated timestamps
  cannot manufacture persistence. Changing a same-name rule resets statistical state.
- Guarded-model capabilities prevent new panels from silently registering with
  an exporter that does not implement the corresponding kernel.

## UI and operations

- Incident timeline avoids duplicate/overlapping endpoint labels.
- Unavailable confidence no longer displays a percentage; data quality is
  categorical instead of misleadingly repeating the confidence percentage.
- Inspector, target-specific query handoff, selected sink, long legends, compact
  charts and responsive layouts are covered by the browser gate.
- Score-feed previews cannot mask backend errors or advance backend heartbeat.
- Source query/scoring timing and input size metrics expose cycle costs.
- Default, Prometheus and InfluxDB configs are included; Python minimum remains 3.9.
- Fresh E2E guide covers installation, source/target separation, all Advanced
  settings, closed-panel feed, alert lifecycle, LB routing, upgrade and rollback.

## Validation and upgrade cautions

The current Linux six-model synthetic precision/F1 and 10k CPU-throughput gate
passed three consecutive recorded runs (minimum 10,493 points/CPU-second).
Earlier variable Linux failures are retained, not erased. Final browser UI
21/21, backend 79/79, Jest 45/45, build/typecheck and 48,201-point TS/Python parity
pass. Live read-only checks pass 13/13. The E2E guide and illustrated PDF are rebuilt.

New reference behavior can change existing scores at unchanged thresholds.
Back up config and the actual dynamic state path; pilot both components together,
compare labeled normal/incident windows, validate fresh target writes after closing
the panel, and test a real firing/resolved recipient before broad rollout.
Recommended profiles do not automatically migrate to Harmonic.

Local synthetic acceptance is not a guarantee of perfect detection on arbitrary
field data. Target-host soak, real delivery and corporate auth/LB remain deployment
acceptance tasks. Keep history, step, bucket and policy identical when comparing scores.
