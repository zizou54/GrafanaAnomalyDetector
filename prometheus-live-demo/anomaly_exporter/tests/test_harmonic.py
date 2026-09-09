from __future__ import annotations

import math
import random
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import asdict
from pathlib import Path

from app.algorithms import evaluate_series
from app.canonical import build_raw_point, score_points
from app.harmonic import HarmonicState, _window_scale
from app.models import RuleConfig, SeriesState
from app.dynamic_rules import DynamicRuleRegistry, RegistrationError
from app.config_loader import load_config, ConfigError


class HarmonicTests(unittest.TestCase):
    def test_correlated_normal_excursions_do_not_lock_the_reference(self):
        for seed in (234012, 234015, 274011, 274012, 274013):
            rng = random.Random(seed)
            values, error = [], 0.
            for _ in range(1440):
                error = .98 * error + math.sqrt(1 - .98 ** 2) * rng.gauss(0, .8)
                values.append(100 + error)
            state = HarmonicState(96, 4)
            scored = [state.update(value) for value in values]
            self.assertLessEqual(sum(max(point[2:]) >= 4 for point in scored[400:]), 20)
            for index in (600, 900, 1200):
                values[index] += 20
            state = HarmonicState(96, 4)
            scored = [state.update(value) for value in values]
            self.assertEqual(sum(max(scored[index][2:]) >= 4 for index in (600, 900, 1200)), 3)

    def test_window_cache_preserves_every_result_and_reduces_work(self):
        rng = random.Random(164019)
        values = [100 + math.sin(i * math.tau / 96) + rng.gauss(0, .8) for i in range(2400)]
        values[900:950] = [120.] * 50
        cached, reference = HarmonicState(96, 4), HarmonicState(96, 4)
        with patch('app.harmonic._window_scale', wraps=_window_scale) as scale:
            results = [cached.update(value) for value in values]
            calls = scale.call_count
        for value, expected in zip(values, results):
            reference.window_key = None
            self.assertEqual(reference.update(value), expected)
        self.assertLess(calls, (len(values) - 192) // 2)

    def test_registration_and_reload_preserve_harmonic_across_source_target_pairs(self):
        kinds = ('prometheus','loki','influxdb','postgresql','clickhouse','elasticsearch')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'state.json'
            registry = DynamicRuleRegistry(path)
            for source in kinds:
                for target in kinds:
                    registry.upsert_panel_registration({
                        'dashboardUid':f'{source}-{target}','panelId':1,'target':target,
                        'capabilitiesRequired':['harmonicScoring'],
                        'targets':[{'refId':'A','expr':'fixture','datasourceType':source,'datasourceUrl':'http://localhost'}],
                        'resolvedOptions':{'algorithm':'harmonic','sensitivity':4,'seasonalitySamples':96}})
            restored = DynamicRuleRegistry(path)
            restored.load()
            self.assertEqual(len(restored.list_records()),36)
            for record in restored.list_records():
                self.assertEqual(record.rule.algorithm,'harmonic')
                self.assertEqual(record.rule.seasonality_samples,96)
            with self.assertRaises(RegistrationError):
                registry.upsert_panel_registration({'dashboardUid':'invalid','panelId':1,'target':'prometheus',
                    'targets':[{'refId':'A','expr':'fixture'}],
                    'resolvedOptions':{'algorithm':'harmonic','seasonalitySamples':2}})

    def test_yaml_harmonic_period_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.yml'
            path.write_text('rules:\n  - name: harmonic\n    query: fixture\n    algorithm: harmonic\n    seasonality_samples: 96\n',encoding='utf-8')
            self.assertEqual(load_config(path).rules[0].algorithm,'harmonic')
            path.write_text(path.read_text().replace('96','2'),encoding='utf-8')
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_stream_replay_all_snapshot_fields_and_decision_policy(self):
        rng = random.Random(133017)
        values = [100 + 4 * math.sin(i * math.tau / 96) + rng.gauss(0, .8) for i in range(1800)]
        values[700:740] = [120.] * 40
        values[1100:1140] = [80.] * 40
        for direction in ('high_or_low', 'high_mean', 'low_mean'):
            rule = RuleConfig(name='harmonic', query='fixture', algorithm='harmonic', seasonality_samples=96,
                              anomaly_direction=direction, persistence_buckets=3, persistence_window=4,
                              recovery_buckets=2, recovery_threshold=3, cooldown_buckets=2)
            replay = score_points(rule, 'fixture', {}, [build_raw_point(i*60., v) for i, v in enumerate(values)])
            state = SeriesState.create(rule.history_limit, rule.baseline_window)
            for i, value in enumerate(values):
                streamed = evaluate_series(state, rule, 'fixture', {}, value, i*60.)
                for key, expected in asdict(replay[i]).items():
                    actual = getattr(streamed, key)
                    if isinstance(expected, float):
                        self.assertAlmostEqual(actual, expected, places=7, msg=f'{direction}/{i}/{key}')
                    else:
                        self.assertEqual(actual, expected, f'{direction}/{i}/{key}')
            self.assertGreater(sum(s.is_anomaly for s in replay), 0)
            count = state.harmonic_state.count
            self.assertIs(evaluate_series(state, rule, 'fixture', {}, 999., (len(values)-1)*60.), state.last_snapshot)
            self.assertEqual(state.harmonic_state.count, count)

    def test_memory_is_bounded_and_warmup_is_two_cycles(self):
        state = HarmonicState(24, 4)
        for i in range(20000):
            scored = state.update(100+math.sin(i))
            self.assertEqual(scored is None, i<48)
        for name, capacity in (('clean',48),('raw',48),('errors',128),('biases',32),('normalized',10)):
            self.assertLessEqual(len(getattr(state,name)),capacity)

    def test_invalid_input_does_not_advance_state(self):
        state = HarmonicState(24, 4)
        with self.assertRaises(ValueError):
            state.update(float('nan'))
        self.assertEqual(state.count,0)
        for period in (1,7,4097):
            with self.assertRaises(ValueError):
                RuleConfig(name='invalid',query='fixture',algorithm='harmonic',seasonality_samples=period)


if __name__ == '__main__':
    unittest.main()
