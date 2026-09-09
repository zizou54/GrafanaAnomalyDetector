"""Untuned, multi-seed characterization. Not a replacement for field acceptance."""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

from detection_quality_check import PROFILES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'prometheus-live-demo' / 'anomaly_exporter'))
from app.canonical import build_raw_point, score_points  # noqa: E402
from app.models import RuleConfig  # noqa: E402

SEEDS = (7, 19, 73, 2026, 4099)
SHAPES = ('stationary', 'seasonal', 'quantized', 'low_activity')
POINTS = 960
EVALUATE_FROM = 320
SPIKES = (480, 720)
SHIFT = range(800, 840)


def fixture(seed: int, shape: str, inject: bool):
    rng = random.Random(seed)
    values = []
    for index in range(POINTS):
        value = 100 + rng.gauss(0, 0.8)
        if shape == 'seasonal':
            value += 4 * math.sin(index * math.tau / 96)
        elif shape == 'quantized':
            value = round(value)
        elif shape == 'low_activity':
            value = abs(rng.gauss(0, 0.02))
        if inject:
            if index in SPIKES:
                value += 20 if index == SPIKES[0] else (-20 if shape != 'low_activity' else 20)
            if index in SHIFT:
                value += 14
        values.append(build_raw_point(float(index * 60), value))
    return values


def measure(rule, points, inject):
    snapshots = score_points(rule, 'fixture', {}, points)
    eligible = set(range(EVALUATE_FROM, len(points)))
    predicted = {index for index in eligible if snapshots[index].is_anomaly}
    truth = set(SPIKES).union(SHIFT) if inject else set()
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    shift_hits = sorted(predicted.intersection(SHIFT))
    high_confidence_normal = sum(index not in truth and snapshots[index].confidence_score >= 95 for index in predicted)
    return dict(tp=tp, fp=fp, fn=fn, background=len(eligible - truth),
                spike_hits=len(predicted.intersection(SPIKES)) if inject else 0,
                shift_detected=int(bool(shift_hits)) if inject else 0,
                shift_delay=shift_hits[0] - SHIFT.start if shift_hits and inject else None,
                high_confidence_fp=high_confidence_normal,
                unscored=sum(snapshots[index].expected is None for index in eligible))


def summarize(rows):
    def total(key):
        return sum(row['metrics'][key] for row in rows)
    tp, fp, fn = total('tp'), total('fp'), total('fn')
    delays = [row['metrics']['shift_delay'] for row in rows if row['metrics']['shift_delay'] is not None]
    positives = sum(row['injected'] for row in rows)
    return dict(cases=len(rows), point_precision=tp / (tp + fp) if tp + fp else None,
                point_recall=tp / (tp + fn) if tp + fn else None,
                fp_points=fp, background_points=total('background'),
                fp_rate=fp / total('background') if total('background') else None,
                spike_recall=total('spike_hits') / (positives * len(SPIKES)) if positives else None,
                shift_recall=total('shift_detected') / positives if positives else None,
                worst_shift_delay=max(delays) if delays else None,
                high_confidence_fp=total('high_confidence_fp'), unscored=total('unscored'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed-start', type=int, help='Use a new contiguous seed cohort instead of the historical cohort.')
    parser.add_argument('--seed-count', type=int, default=5)
    args = parser.parse_args()
    if args.seed_count < 1:
        parser.error('--seed-count must be positive')
    seeds = SEEDS if args.seed_start is None else tuple(range(args.seed_start, args.seed_start + args.seed_count))
    rows = []
    policies = {'raw': {}, '3of4': {'persistence_buckets': 3, 'persistence_window': 4},
                '3of4_floor': {'persistence_buckets': 3, 'persistence_window': 4,
                              'minimum_absolute_deviation': 3, 'minimum_relative_deviation': 0.05},
                'lifecycle': {'persistence_buckets': 3, 'persistence_window': 4,
                              'recovery_buckets': 2, 'cooldown_buckets': 2, 'data_quality_gate': True}}
    for algorithm, profile in PROFILES.items():
        base = RuleConfig(name='holdout', query='fixture', algorithm=algorithm,
                          threshold=profile.threshold, baseline_window=profile.baseline_window,
                          seasonality_samples=96, seasonal_refinement='cycle')
        for policy, settings in policies.items():
            effective_settings = dict(settings)
            if policy == 'lifecycle':
                effective_settings['recovery_threshold'] = profile.threshold * 0.75
            for seed in seeds:
                for shape in SHAPES:
                    for inject in (False, True):
                        rows.append(dict(algorithm=algorithm, policy=policy, seed=seed, shape=shape,
                                         injected=inject, metrics=measure(replace(base, **effective_settings), fixture(seed, shape, inject), inject)))
    summaries = {}
    print('algorithm   policy      normal_FP_rate event_precision spike_recall shift_recall high_conf_FP')
    for algorithm in PROFILES:
        for policy in policies:
            selected = [row for row in rows if row['algorithm'] == algorithm and row['policy'] == policy]
            controls = summarize([row for row in selected if not row['injected']])
            events = summarize([row for row in selected if row['injected']])
            summaries[f'{algorithm}/{policy}'] = dict(controls=controls, events=events)
            precision = 'n/a' if events['point_precision'] is None else f"{events['point_precision']:.3f}"
            print(f"{algorithm:11} {policy:11} {controls['fp_rate']:14.4f} {precision:>15} "
                  f"{events['spike_recall']:12.3f} {events['shift_recall']:12.3f} {controls['high_confidence_fp']:12}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(
        interpretation='Characterization only; no thresholds fitted, no production PASS implied. Confidence is not probability. Lifecycle uses recovery_threshold=0.75*threshold. Tests raw-point input; not the full UI recommended profile (direction/preset/bucketing can differ).',
        seeds=seeds, point_count=POINTS, evaluate_from=EVALUATE_FROM, policies=policies,
        parameters={name: {**vars(profile), 'seasonality_samples': 96} for name, profile in PROFILES.items()},
        summaries=summaries, rows=rows,
    ), indent=2), encoding='utf-8')
    print(f'[COMPLETE] {len(rows)} cases; raw scorer defaults and strict quality gate unchanged.')


if __name__ == '__main__':
    main()
