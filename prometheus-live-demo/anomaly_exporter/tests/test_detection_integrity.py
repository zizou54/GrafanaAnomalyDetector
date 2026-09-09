from __future__ import annotations

import unittest
import io
import json
import math
from copy import deepcopy
from unittest.mock import patch

from app.algorithms import evaluate_series
from app.canonical import build_raw_point, score_points
from app.models import RuleConfig, SeriesState
from app.prometheus_api import PrometheusClient


ALGORITHMS = ('zscore', 'mad', 'ewma', 'seasonal', 'level_shift')


class DetectionIntegrityTests(unittest.TestCase):
    def test_stream_and_batch_match_after_history_rollover(self):
        for algorithm in ALGORITHMS:
            for window in (3, 12, 30):
                with self.subTest(algorithm=algorithm, window=window):
                    rule = RuleConfig(name='rollover', query='fixture', algorithm=algorithm,
                                      threshold=4, baseline_window=window, seasonality_samples=4)
                    points = [build_raw_point(float(index * 60), 100 + math.sin(index / 9) + (15 if index % 71 == 0 else 0))
                              for index in range(600)]
                    batch = score_points(rule, 'fixture', {}, points)
                    state = SeriesState.create(rule.history_limit, rule.baseline_window)
                    for point, expected in zip(points, batch):
                        actual = evaluate_series(state, rule, 'fixture', {}, point.value, point.time)
                        self.assertEqual(actual.is_anomaly, expected.is_anomaly)
                        self.assertEqual(actual.data_quality_label, expected.data_quality_label)
                        self.assertEqual(actual.confidence_score, expected.confidence_score)
                        self.assertAlmostEqual(actual.raw_score, expected.raw_score, places=6)
                        self.assertEqual(actual.normalized_score, expected.normalized_score)

    def test_prometheus_nonfinite_or_missing_samples_never_enter_the_baseline(self):
        bad_pairs = [[100, 'NaN'], [100, '+Inf'], [100, '-Inf'], ['NaN', '10'],
                     [100, 'not-a-number'], None, [], [100]]
        client = PrometheusClient('http://fixture.invalid', 1)
        for kind in ('vector', 'scalar', 'matrix'):
            for pair in bad_pairs:
                with self.subTest(kind=kind, pair=pair):
                    if kind == 'scalar':
                        result = pair
                    else:
                        result = [{'metric': {'instance': 'bad'},
                                   'value' if kind == 'vector' else 'values': pair if kind == 'vector' else [pair]}]
                    payload = {'status': 'success', 'data': {'resultType': kind, 'result': result}}
                    with patch('app.prometheus_api.open_same_origin', return_value=io.BytesIO(json.dumps(payload).encode())):
                        actual = client.range_query('fixture', 0, 100, 1) if kind == 'matrix' else client.instant_query('fixture', 100)
                    self.assertEqual(actual, [], 'missing/invalid data is not a healthy zero sample')

    def test_prometheus_zero_is_valid_and_invalid_series_does_not_drop_healthy_series(self):
        payload = {'status': 'success', 'data': {'resultType': 'vector', 'result': [
            {'metric': {'instance': 'bad'}, 'value': [100, 'NaN']},
            {'metric': {'instance': 'missing'}},
            {'metric': {'instance': 'good'}, 'value': [100, '0']},
        ]}}
        with patch('app.prometheus_api.open_same_origin', return_value=io.BytesIO(json.dumps(payload).encode())):
            samples = PrometheusClient('http://fixture.invalid', 1).instant_query('fixture', 100)
        self.assertEqual([(sample.labels['instance'], sample.value) for sample in samples], [('good', 0)])

    def test_repeated_sample_cannot_satisfy_persistence(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                rule = RuleConfig(name='repeat', query='fixture', algorithm=algorithm,
                                  threshold=4, baseline_window=12, seasonality_samples=4,
                                  persistence_buckets=3, persistence_window=4)
                state = SeriesState.create(rule.history_limit, rule.baseline_window)
                for index in range(48):
                    evaluate_series(state, rule, 'fixture', {}, 100 + index % 2, float(index))
                first = evaluate_series(state, rule, 'fixture', {}, 180, 48.0)
                self.assertFalse(first.is_anomaly)
                before = deepcopy(state)
                for _ in range(8):
                    repeated = evaluate_series(state, rule, 'fixture', {}, 180, 48.0)
                    self.assertEqual(repeated, first)
                    self.assertEqual(state, before, 'polling is not a new observation')
                evaluate_series(state, rule, 'fixture', {}, 180, 49.0)
                confirmed = evaluate_series(state, rule, 'fixture', {}, 180, 50.0)
                unique_values = [100 + index % 2 for index in range(48)] + [180] * 3
                batch = score_points(rule, 'fixture', {}, [build_raw_point(float(index), value)
                                                          for index, value in enumerate(unique_values)])
                self.assertEqual(confirmed.is_anomaly, batch[-1].is_anomaly)
                self.assertEqual(confirmed.decision_state, batch[-1].decision_state)
                if algorithm == 'mad':
                    self.assertTrue(confirmed.is_anomaly)

    def test_late_sample_cannot_rewind_streaming_state(self):
        rule = RuleConfig(name='late', query='fixture', algorithm='ewma')
        state = SeriesState.create(rule.history_limit, rule.baseline_window)
        latest = evaluate_series(state, rule, 'fixture', {}, 100, 100.0)
        before = deepcopy(state)
        result = evaluate_series(state, rule, 'fixture', {}, 9999, 99.0)
        self.assertEqual(result, latest)
        self.assertEqual(state, before)

    def test_streaming_quality_gate_matches_panel_batch_for_gaps_and_flatlines(self):
        for algorithm in ALGORITHMS:
            for gate in (False, True):
                for scenario in ('flat_to_spike', 'gap_to_spike'):
                    with self.subTest(algorithm=algorithm, gate=gate, scenario=scenario):
                        rule = RuleConfig(name='quality', query='fixture', algorithm=algorithm,
                                          threshold=4, baseline_window=12, seasonality_samples=4,
                                          data_quality_gate=gate)
                        values = [100.0 + (index % 2 if scenario == 'gap_to_spike' else 0)
                                  for index in range(48)] + [180.0]
                        points = [build_raw_point(float(index * 60), value)
                                  for index, value in enumerate(values)]
                        if scenario == 'gap_to_spike':
                            points[-1] = build_raw_point(points[-1].time + 3600, values[-1])
                        batch = score_points(rule, 'fixture', {}, points)
                        state = SeriesState.create(rule.history_limit, rule.baseline_window)
                        stream = [evaluate_series(state, rule, 'fixture', {}, point.value, point.time)
                                  for point in points]
                        self.assertEqual(stream[-1].data_quality_label, batch[-1].data_quality_label)
                        self.assertEqual(stream[-1].is_anomaly, batch[-1].is_anomaly)
                        self.assertEqual(stream[-1].normalized_score, batch[-1].normalized_score)
                        self.assertEqual(stream[-1].confidence_score, batch[-1].confidence_score)
                        if scenario == 'gap_to_spike' and gate:
                            self.assertFalse(stream[-1].is_anomaly)


if __name__ == '__main__':
    unittest.main()
