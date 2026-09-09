"""Qualify the integrated Harmonic scorer without altering the five legacy gates."""
from __future__ import annotations

import json
import math
import random
import argparse
from detection_holdout_check import fixture, EVALUATE_FROM, SHIFT, SPIKES

from detection_quality_check import PROFILES, AlgorithmProfile, build_scenario, evaluate, production_quality_failures
from app.canonical import build_raw_point, score_points
from app.models import RuleConfig


def integrated_predictions(values):
    rule = RuleConfig(name='holdout', query='fixture', algorithm='harmonic',
                      threshold=4, seasonality_samples=96)
    snapshots = score_points(rule, 'fixture', {}, [build_raw_point(i * 60., v) for i, v in enumerate(values)])
    return {i for i, point in enumerate(snapshots) if point.is_anomaly}


def holdout_failures(seed_start=174011, predict=None, include_periodic_shapes=True):
    predict = predict or integrated_predictions
    failures = []
    for shape in ('stationary', 'seasonal', 'quantized', 'low_activity'):
        tp = fp = fn = normal_fp = eligible = hits = 0
        for seed in range(seed_start, seed_start + 5):
            for injected in (False, True):
                values = [p.value for p in fixture(seed, shape, injected)]
                predicted = predict(values) & set(range(EVALUATE_FROM, len(values)))
                if injected:
                    truth = set(SPIKES) | set(SHIFT)
                    tp += len(predicted & truth)
                    fp += len(predicted - truth)
                    fn += len(truth - predicted)
                    hits += len(predicted & set(SPIKES))
                else:
                    normal_fp += len(predicted)
                    eligible += len(values) - EVALUATE_FROM
        precision = tp / (tp + fp) if tp + fp else 0.
        f1 = 2 * tp / (2 * tp + fp + fn)
        print(json.dumps(dict(holdout=shape, seed_start=seed_start, seed_count=5,
                              precision=precision, f1=f1, normal_fp=normal_fp,
                              eligible=eligible, spike_hits=hits, spike_count=10)), flush=True)
        if precision < .7 or f1 < .6 or normal_fp / eligible > .02 or hits / 10 < .9:
            failures.append(f'holdout/{shape}: precision/F1/normal FP/spike recall')
    if not include_periodic_shapes:
        return failures
    for shape in ('square', 'sawtooth', 'double_period', 'linear_trend'):
        fp = 0
        for seed in range(seed_start + 1000, seed_start + 1005):
            rng = random.Random(seed)
            values = []
            for i in range(960):
                signal = (4 if i % 96 < 48 else -4) if shape == 'square' else (
                    8 * (i % 96) / 96 - 4 if shape == 'sawtooth' else (
                    4 * math.sin(i * math.tau / 48) if shape == 'double_period' else i * .03))
                values.append(100 + signal + rng.gauss(0, .8))
            fp += len(predict(values) & set(range(320, 960)))
        print(json.dumps(dict(normal_shape=shape, fp=fp, eligible=3200)), flush=True)
        if fp / 3200 > .02:
            failures.append(f'holdout/{shape}: normal FP above 2%')
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-start', type=int, default=174011)
    parser.add_argument('--ar-seed-start', type=int, default=154011)
    args = parser.parse_args(argv)
    # Local extra profile; never replace existing algorithms or acceptance limits.
    PROFILES['harmonic'] = AlgorithmProfile(4, 12, 144)
    results = {name: {'harmonic': evaluate('harmonic', values)} for name, values in (
        ('clear', build_scenario(noise=.8, spike=20, shift=14)),
        ('hard', build_scenario(noise=2.5, spike=12, shift=8)))}
    failures = production_quality_failures(results)
    for name, rows in results.items():
        metrics = rows['harmonic']
        print(json.dumps(dict(scenario=name, **metrics)), flush=True)
        if metrics['warmup_breaches']:
            failures.append(f'{name}: warm-up breach')
        if metrics['points_per_second'] < 10000:
            failures.append(f'{name}: integrated throughput below 10k points/CPU-second')
    rule = RuleConfig(name='control', query='fixture', algorithm='harmonic', seasonality_samples=96)
    for rho in (0., .5, .9, .98):
        fp = hits = 0
        for seed in range(args.ar_seed_start, args.ar_seed_start + 5):
            rng = random.Random(seed)
            error = 0.
            values = []
            for i in range(1440):
                error = rho * error + math.sqrt(1-rho*rho) * rng.gauss(0,.8)
                values.append(100+error)
            normal = score_points(rule,'fixture',{},[build_raw_point(i*60.,v) for i,v in enumerate(values)])
            fp += sum(p.is_anomaly for p in normal[400:])
            for i, delta in ((600,20),(900,-20),(1200,20)):
                values[i] += delta
            injected = score_points(rule,'fixture',{},[build_raw_point(i*60.,v) for i,v in enumerate(values)])
            hits += sum(injected[i].is_anomaly for i in (600,900,1200))
        print(json.dumps(dict(rho=rho,seed_start=args.ar_seed_start,normal_fp=fp,eligible=5200,spike_hits=hits,spike_count=15)),flush=True)
        if fp/5200>.02 or hits/15<.9:
            failures.append(f'AR(1) rho={rho}: normal FP / recall')
    failures.extend(holdout_failures(args.seed_start))
    print(json.dumps(dict(passed=not failures, failures=failures,
                          scope='Integrated Harmonic only; not qualification of all legacy algorithms or field data')),flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
