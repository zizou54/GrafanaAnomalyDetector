# Changelog

## 1.5.1 (2026-09-09)

- Prevent overlapping timeline labels and unavailable percentages. Display data quality categorically instead of duplicating confidence. Final browser suite after display fixes: 21/21 passing. Linux strict gate: three consecutive passes; field-only acceptance remains required.

- Align guarded seasonal cycle scoring (period >=8) and level-shift reference/window scoring with the exporter. Preserve short-cycle/calendar behavior and require matching scoring capabilities on registration. Production threshold backtesting remains required.

- Align guarded EWMA scoring with the exporter, damp stale trend during guarded events, and require the `guardedEwmaScoring` capability. This changes EWMA score behavior; deploy matched plugin/exporter builds and revalidate existing thresholds before production rollout.

- Add opt-in Harmonic (known cycle) for matched exporter 1.5.1, with an explicit period and two-cycle warm-up. Existing algorithm selections are unchanged; this is not blanket production qualification.
- Align guarded rolling z-score/MAD scoring with the exporter, including persistent-event reference protection and correlation-aware window evidence. Require `guardedRollingScoring` capability before registration; existing selections stay unchanged but their score behavior is revised.

- Correct chronological ordering of seasonal-cycle trend peers, identically in panel and exporter.
- Stop historical window evidence from opening anomalies on recovered or opposite-direction current points; preserve explicit recovery policy.
- Validate scoring parity and independent holdouts. The six-model strict quality/performance gate passes three consecutive Linux runs with both scenarios enforced; earlier speed failures remain in historical evidence. No zero-false-positive or unconditional field-acceptance claim.
- Match exporter 1.5.1 and provide version-matched packages, sample configurations and rebuilt E2E documentation.

## 1.5.0-r1 (2026-09-04; package revision)

- Keep application version 1.5.0 while giving both ZIPs versioned names and build manifests.
- Normalize unknown detection direction and show a configuration warning.
- Observe chart size after delayed mounting, fit compact chart-only panels, and prevent time-axis caption overlap.
- Ship the reviewed API diagnostics fixes with the matched exporter bundle and default/Prometheus/Influx YAML examples.
- Record strict detection-quality and throughput limitations explicitly; no unconditional production approval.

## 1.5.0 (2026-09-03)

- Added Elastic-style anomaly direction controls for high-mean, low-mean, and two-sided deviations.
- Added decision floors, minimum activity, N-of-M persistence, and degraded-data blocking to Advanced tuning and recommended presets.
- Added exporter API capability negotiation and actionable diagnostics for empty, HTML, metrics, proxy, and CORS failures.
- Added deterministic scope-aware score-feed registration compatible with exporter API schema 3.
- Added interactive legend isolation/hiding, full scrollable series lists, and chart-only responsive reflow without changing score-feed coverage.
- Added recovery hysteresis, recovery-bucket, and cooldown controls with visible candidate/open/recovering decision states.
- Added searchable/sortable high-cardinality legends and target-specific active-incident alert queries.
- Fixed status-header overflow in narrow dashboard grid panels by using panel container width for responsive reflow.

## 1.4.0 (2026-08-16)

- Fixed Grafana datasource legend and display-name propagation across the anomaly chart, tooltip, inspector, incident feed, score feed, and exporter recompute flow.
- Added persistent, backward-compatible visibility controls for the panel's major operational sections.
- Replaced direct anomaly-threshold number entry with a keyboard-accessible slider and clear Sensitive, Balanced, and Strict guidance.
- Removed the redundant threshold visibility switch; threshold tuning now appears automatically in Advanced mode.
- Added a full-history warm-up guard to prevent range-boundary false positives in panel and exporter scoring paths.

## 1.3.0 (2026-06-10)

- Added canonical scorer parity with the exporter for plugin-computed score feed flows.
- Added target-aware score feed actions for Prometheus, Loki, InfluxDB, PostgreSQL, ClickHouse, and Elasticsearch outputs.
- Fixed the peak score stat to use the normalized 0-100 severity score.
- Improved `level_shift` sustained-shift handling by keeping an older stable baseline reference.

## 1.2.1 (2026-04-02)

- Fixed chart rendering in Grafana `viewPanel`, `editPanel`, and constrained dashboard layouts by sizing the SVG against the real card container instead of relying on panel height guesses.
- Added resize-aware regression coverage for `editPanel`, `viewPanel`, `d-solo`, narrow layouts, and redraw flows to prevent chart clipping and crushed line rendering from returning.
- Re-validated responsive score-feed scenarios on live Grafana `11.6.7` and `12.4.1` stacks.

## 1.2.0 (2026-03-28)

- Added a new `level_shift` detector and a dedicated `Subtle level shift / drift` preset for sustained baseline changes.
- Tuned the recommended presets to align with the benchmark findings for traffic, latency, error, resource, and business metrics.
- Added confidence and data-quality scoring to both the panel and Prometheus exporter so operators can judge whether a signal is strong enough for alerting.
- Reworked the panel UX with grouped incidents, a clearer anomaly inspector, confidence-aware markers, and more operator-friendly wording.
- Expanded annotation and alert export payloads with confidence and data-quality fields for easier downstream automation.

## 1.0.0

Initial release.
