"""Capture local lab source samples for offline, timestamp-aligned TS/Python parity."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, '/app')
from app.canonical import aggregate_raw_points, build_raw_point
from app.config_loader import load_config
from app.dynamic_rules import DynamicRuleRegistry
from app.sources import build_source_reader

config = load_config(Path('/app/config.yml'))
records = [r for r in DynamicRuleRegistry('/app/state/dynamic_rules.json').list_records()
           if r.dashboard_uid == 'plugin-source-matrix' and r.scope_policy == 'saved'
           and r.scope_hash == 'saved' and 2 <= r.panel_id <= 7]
assert len(records) == 6
now = time.time()
cases = []
for record in records:
    rule = record.rule
    step = rule.step_seconds or config.global_config.evaluation_interval_seconds
    start = now - (rule.range_seconds or max(rule.history_limit * step, step * 4))
    matrix = build_source_reader(rule, config.global_config).query_range(start, now, step)
    assert matrix, record.rule.name
    for index, series in enumerate(matrix):
        raw = aggregate_raw_points([build_raw_point(p.timestamp, p.value) for p in series.samples],
                                   rule.bucket_span_seconds or None)
        if not raw:
            continue
        options = {'algorithm': rule.algorithm, 'sensitivity': rule.threshold,
                   'baselineWindow': rule.baseline_window, 'seasonalitySamples': rule.seasonality_samples,
                   'seasonalRefinement': rule.seasonal_refinement, 'severityPreset': rule.severity_preset}
        for key in ('anomaly_direction', 'minimum_absolute_deviation', 'minimum_relative_deviation',
                    'minimum_activity', 'persistence_buckets', 'persistence_window',
                    'recovery_threshold', 'recovery_buckets', 'cooldown_buckets', 'data_quality_gate'):
            first, *rest = key.split('_')
            options[first + ''.join(part.title() for part in rest)] = getattr(rule, key)
        cases.append(dict(name=rule.name + '_' + str(index), source=rule.source_type, options=options,
                          points=[dict(timestamp=p.time, value=p.value) for p in raw]))
print(json.dumps(cases, allow_nan=False))
