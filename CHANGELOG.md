# Changelog

## 1.5.1 (2026-09-09)

- Re-run Linux synthetic quality/CPU throughput: three consecutive recorded full passes, minimum 10,493 points/CPU-second; retain earlier failures and deployment limits. Add a non-overwriting temporary UI fixture runner and assert actual clipboard content rather than transient success toasts.
- Rebuild the versioned E2E guide, Advanced configuration reference, package inventory and release notes. Require explicit package revision and committed, version-matched package inputs to prevent stale documentation/provenance.

- Verify local deploy, 36 closed-panel source/target routes, six-source captured score parity, and five sink recoveries. Earlier Linux failures remain in `docs/LOCAL_DEPLOY_ACCEPTANCE_151_TR.md`; three fresh consecutive Linux runs now pass. See `release/STATUS_v1.5.1.md` for current scope.
- Avoid duplicate/overlapping incident timeline endpoint labels. Make TestData E2E skip only on a real missing dashboard, use explicit single-spike policy, and assert current inspector values.

- Enforce the 10k CPU-throughput gate separately for all six models in both clear and hard scenarios, including invalid-measurement rejection. Three consecutive local runs pass; retain earlier speed failures and do not infer hardware-independent performance. Reuse sorted noise samples and the EWMA point scale without changing scores; revalidate 79 backend tests and 48,201 TS/Python parity points.

- Use guarded phase peers and confidence-gated drift correction for seasonal cycle periods >=8; retain short-cycle and calendar refinements. Add `guardedSeasonalScoring` registration capability.
- Replace the level-shift detector's stale anchor with the shared damped exponential reference and correlated window evidence. Retain its baseline-dependent evidence window and 0.85 point weight; add `guardedLevelShiftScoring`. This is a behavioral change, not an alias or threshold-only tuning.

- Replace EWMA's anomaly-contaminated reference with bounded guarded double exponential smoothing and damped trend during anomalies. Align panel, replay and streaming; require `guardedEwmaScoring` for panel registration. All six models pass the local strict synthetic gate; field-data acceptance remains required.

- Add opt-in Harmonic (known cycle) in the panel, canonical replay, streaming evaluator and dynamic registration. Requires 8-4096 scored samples per cycle and two cycles of warm-up; existing Recommended profiles and rules are not migrated.
- Bound harmonic memory, correct correlated-noise evidence and quantized-series spread; test all snapshot/decision fields across TS/Python and stream/replay. Harmonic passes the measured integrated 10k CPU-throughput gate; hardware-independent performance is not claimed.
- Guard rolling z-score/MAD reference updates against persistent deviations, pool bounded residual noise and account for correlated evidence. Keep mean/median model identities and the shared direction/persistence/recovery policies; matched exporters must advertise `guardedRollingScoring`.
- Avoid copying already normalized read-only scorer input, cache noise/window statistics and use an equivalent regular-cadence quality path. Tests cover ownership, duplicate samples, malformed metadata and stream/replay parity.

- Fix reversed chronological peer ordering in seasonal cycle trend estimation in both panel and exporter.
- Require current-point direction/deviation support for historical window evidence; recovered points no longer open an anomaly solely because of an older window. Explicit recovery persistence remains configurable.
- Align streaming data-quality/confidence with batch scoring, deduplicate source timestamps, and reject missing/non-finite Prometheus samples without converting them to healthy zeros.
- Reset statistical state when a same-name rule changes; prevent panel previews from masking backend failures or advancing backend heartbeat metrics.
- Fix Windows registry backup fsync and avoid mutating source configuration during endpoint resolution.
- Retain paired validation and extend independent holdouts and regression tests. Windows and three fresh Linux runs pass strict precision/F1 and both-scenario throughput. Earlier clear-only gate results are not complete speed acceptance. No blanket production acceptance or zero-false-positive claim.
- Correct unavailable percentages and remove misleading confidence-as-quality percentages; final UI suite 21/21. Plugin/exporter versions are 1.5.1, API schema remains 3; matched ZIPs include sample configs and rebuilt documentation.

## 1.5.0-r1 (package revision; application version remains 1.5.0)

- Publish the reviewed post-release fixes with versioned plugin/exporter ZIP names and per-file build manifests. The original v1.5.0 tag/assets remain unchanged.
- Normalize unknown anomaly direction consistently in panel/exporter and display a panel configuration warning.
- Return a clean JSON 400 for invalid panel deletion IDs; expose diagnostic request/version headers to browsers.
- Attach chart resize observation after delayed mounting, fit compact chart-only panels, and separate time ticks from the axis caption.
- Correct point-F1 reporting and distinguish the strict quality gate from the historical regression check. Strict synthetic detection quality still has open findings; this revision is not unconditional production acceptance.
- Include validated default, Prometheus and InfluxDB YAML configurations, empty distribution state, and same-origin /anomalyalarm proxy guidance.

## 1.5.0

- Added user-configurable Elastic-style `high_mean`, `low_mean`, and `high_or_low` anomaly direction policies with identical panel and exporter behavior.
- Added minimum absolute/relative deviation, minimum activity, N-of-M persistence, and degraded-data decision gates.
- Added root and configurable base-path API aliases, structured JSON errors, capabilities negotiation, bounded request bodies, CORS allowlists, optional bearer authentication, and datasource host allowlists.
- Made dynamic rule registration thread-safe, idempotent, scope-aware, revision-aware, and crash-safe with atomic state writes and backup recovery.
- Added dynamic state health and registration counters to the Prometheus exporter metrics.
- Added interactive series isolate/hide controls, complete scrollable legends/tooltips, and responsive chart-only layout behavior.
- Added recovery-threshold hysteresis, consecutive recovery buckets, cooldown, and explicit candidate/open/recovering lifecycle states with TypeScript/Python parity.
- Added separate live, ready, and dependency health endpoints plus per-rule anomaly, decision-state, data-state, and last-sample metrics.
- Added dynamic-rule quotas, runtime-scope TTL, feed-preview TTL, explicit panel deletion, request rate limiting, same-origin redirect enforcement, and valid Prometheus label normalization.
- Fixed multi-table InfluxDB annotated CSV parsing so changing tag schemas cannot corrupt source labels or create cardinality noise.
- Fixed narrow dashboard panels to reflow status metadata and KPI cards based on panel width rather than browser viewport width.

## 1.4.0

- Preserved Grafana legends and aliases from datasource frames through panel views, exported score records, and dashboard-closed exporter recomputation.
- Added per-panel visibility controls for major Anomaly Detector sections with legacy defaults and automatic grid reflow.
- Added a `0.2` to `10.0` anomaly-threshold slider with semantic Sensitive, Balanced, and Strict guidance.
- Removed the redundant threshold visibility switch and made threshold tuning automatically available in Advanced mode.
- Added matching panel/exporter warm-up behavior so range-boundary points cannot alert before the configured history window is complete.
- Added a reproducible detection quality gate covering event recall, false-positive rate, warm-up behavior, and scorer throughput.

## 1.3.0

- Added optional multi-datasource anomaly feed sinks for Loki, InfluxDB, PostgreSQL, ClickHouse, and Elasticsearch.
- Kept the existing Prometheus exposition and score-feed sync flow intact; `sinks:` is fully optional.
- Added sink health metrics under `grafana_anomaly_sink_*`.
- Added sink queue/backpressure metrics and HTTP `429` feedback when non-Prometheus feed targets cannot queue writes.
- Added an exporter build info metric with the `1.3.0` version label.
- Added a WSL-friendly `multi-sink-demo/` stack with pinned backend images, read-back checks, and datasource-specific example alert rules.
- Added exporter unit/smoke tests for config fallback parsing, Loki runtime integration, HTTP sink payloads, and PostgreSQL optional-driver fallback.
- Fixed PostgreSQL sink reconnection after backend restarts by invalidating stale connections after write errors.
- Hardened canonical scoring against NaN/Inf input points and improved `level_shift` sustained-shift handling.
- Optimized `level_shift` after retest so benchmark throughput is again above 10k points/sec.
- Fixed anomaly panel legend `max` values to display normalized 0-100 severity scores.

## 1.2.1

- Stabilized Grafana panel rendering in `viewPanel`, `editPanel`, `d-solo`, narrow layouts, and resize/redraw flows.
