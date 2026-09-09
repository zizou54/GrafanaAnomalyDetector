"""Read-only local demo check. No registry writes, alert mutations or sink inserts."""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, '/app')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'prometheus-live-demo/anomaly_exporter'))
from app.alert_queries import build_score_feed_registration
from app.canonical import aggregate_raw_points, build_raw_point, score_points
from app.config_loader import load_config
from app.dynamic_rules import DynamicRuleRegistry
from app.models import RuleConfig
from app.sources import build_source_reader, normalize_source_type


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='/app/config.yml')
    parser.add_argument('--state', default='/app/state/dynamic_rules.json')
    args = parser.parse_args()
    config = load_config(Path(args.config))
    registry = DynamicRuleRegistry(Path(args.state))
    registry.load()
    now = time.time()
    rows = []
    for record in registry.list_records():
        if not record.rule.name.startswith('local_'):
            continue
        rule = replace(record.rule)
        step = rule.step_seconds or config.global_config.evaluation_interval_seconds
        start = now - (rule.range_seconds or max(rule.history_limit * step, step * 4))
        matrix = build_source_reader(rule, config.global_config).query_range(start, now, step)
        snapshots = []
        for series in matrix:
            raw = [build_raw_point(sample.timestamp, sample.value) for sample in series.samples]
            scored = score_points(rule, 'fixture', {}, aggregate_raw_points(raw, rule.bucket_span_seconds or None))
            if scored:
                snapshots.append(scored[-1])
        registration = build_score_feed_registration(rule.name, record.target, config)
        read_query = registration['query']
        if record.target == 'elasticsearch':
            # The alert helper returns a setup recipe, not an Elasticsearch DSL request.
            recipe = json.loads(read_query)
            read_query = json.dumps({'query': recipe['query'], 'timeField': recipe['timeField'],
                                     'metrics': [{'type': 'max', 'field': 'normalized_score'}],
                                     'bucketAggs': [{'type': 'date_histogram', 'field': '@timestamp',
                                                     'settings': {'interval': '1m'}}]})
        read_rule = RuleConfig(name='readback', query=read_query, source_type=record.target)
        read_matrix = build_source_reader(read_rule, config.global_config).query_range(now - 120, now, 5)
        samples = [sample for series in read_matrix for sample in series.samples if math.isfinite(sample.value)]
        latest = max((sample.timestamp for series in matrix for sample in series.samples), default=0)
        row = dict(source=normalize_source_type(rule.source_type), target=record.target,
                   series=len(matrix), source_samples=sum(len(series.samples) for series in matrix),
                   trained_series=sum(snapshot.expected is not None for snapshot in snapshots),
                   source_age_seconds=round(now - latest, 2), target_query_samples=len(samples),
                   target_last_timestamp=max((sample.timestamp for sample in samples), default=0))
        row['pass'] = bool(matrix and samples and any(snapshot.expected is not None for snapshot in snapshots)
                           and row['source_age_seconds'] <= max(120, step * 3))
        rows.append(row)
        print(json.dumps(row), flush=True)
    passed = len(rows) == 6 and all(row['pass'] for row in rows)
    print(json.dumps(dict(pass_all=passed, routes=len(rows),
                         scope='6 saved demo routes, live read and target alert-query readback; not all 36 pairs or timestamp-aligned score parity')))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
