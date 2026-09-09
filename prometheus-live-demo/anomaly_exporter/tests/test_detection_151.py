from __future__ import annotations

import unittest
from statistics import median

from app.canonical import _window_score, build_raw_point, score_points
from app.models import RuleConfig


class Detection151Tests(unittest.TestCase):
    def test_cycle_trend_uses_chronological_peers_in_both_directions(self):
        for direction in (-1, 1):
            rule = RuleConfig(name='trend', query='fixture', algorithm='seasonal',
                              baseline_window=3, seasonality_samples=4)
            values = [100 + direction * (i // 4) * 2 + i % 4 for i in range(25)]
            result = score_points(rule, 'fixture', {}, [build_raw_point(i * 60., v) for i, v in enumerate(values)])
            peers = [values[i] for i in (12, 16, 20)]
            expected = median(peers) + median([peers[1]-peers[0], peers[2]-peers[1]])
            self.assertEqual(result[-1].expected, expected)

    def test_window_evidence_requires_current_direction_and_deviation(self):
        self.assertEqual(_window_score([120.] * 9, 100., 100., 1., 30), 0.)
        self.assertEqual(_window_score([120.] * 9, 98., 100., 1., 30), 0.)
        self.assertGreater(_window_score([120.] * 9, 120., 100., 1., 30), 4.)

    def test_return_to_baseline_is_not_a_new_level_shift(self):
        rule = RuleConfig(name='recovery', query='fixture', algorithm='level_shift', baseline_window=30)
        values = [100 + (.5 if i % 2 else -.5) for i in range(60)] + [130.] * 6 + [100.]
        scores = score_points(rule, 'fixture', {}, [build_raw_point(i * 60., v) for i, v in enumerate(values)])
        self.assertTrue(scores[-2].is_anomaly)
        self.assertFalse(scores[-1].is_anomaly)
        self.assertEqual(scores[-1].window_raw_score, 0.)


if __name__ == '__main__':
    unittest.main()
