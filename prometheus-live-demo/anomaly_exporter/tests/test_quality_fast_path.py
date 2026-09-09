from __future__ import annotations

import random
import unittest

from app.canonical import (_data_quality_state, _data_quality_state_from_arrays,
                           _data_quality_states, _bound_raw_score, build_raw_point, score_points,
                           _scoring_points, _valid_raw_points, dedupe_consecutive_points)
from app.models import RuleConfig


class QualityFastPathTests(unittest.TestCase):
    def test_batch_cadence_fast_path_matches_reference_including_future_gaps(self):
        rng = random.Random(244019)
        for step_choices in ((1.,), (1., 1.8), (1., 1.8001), (0., 1., -1., 10.)):
            t = 0.
            points = []
            for i in range(500):
                t += rng.choice(step_choices)
                points.append(build_raw_point(t, 100. if i % 80 < 12 else 100. + rng.gauss(0, 1)))
            for window in (3, 8, 12, 128):
                expected = [_data_quality_state(points, i, window) for i in range(len(points))]
                self.assertEqual(_data_quality_states(points, window), expected)
                self.assertEqual(_data_quality_states(points[:300], window), expected[:300])

    def test_score_clamp_is_equivalent_for_finite_and_nonfinite_inputs(self):
        import math
        values = [-float('inf'), float('nan'), float('inf'), -0., 0., -1., 100., 101.]
        values += [random.Random(seed).uniform(-1000, 1000) for seed in range(300)]
        for value in values:
            expected = max(0., min(100., value)) if math.isfinite(value) else 0.
            self.assertEqual(_bound_raw_score(value), expected)
            self.assertEqual(math.copysign(1., _bound_raw_score(value)), math.copysign(1., expected))

    def test_array_quality_matches_reference_over_random_cadence_and_windows(self):
        rng = random.Random(420173)
        for window in (3, 4, 8, 12, 128):
            times, values = [], []
            t = 0.
            for i in range(1000):
                t += rng.choice((0., -1., 1., 1., 1.8, 2.4, 10.))
                times.append(t)
                values.append(100. if i % 80 < 12 else 100. + rng.gauss(0, 1))
            points = [build_raw_point(t, v) for t, v in zip(times, values)]
            for i in range(len(points)):
                self.assertEqual(_data_quality_state_from_arrays(values, times, i, window),
                                 _data_quality_state(points, i, window), (window, i))

    def test_normalization_and_duplicate_merge_do_not_mutate_input(self):
        points = [build_raw_point(1., 10.), build_raw_point(1., 20.), build_raw_point(2., 30.)]
        before = [vars(point).copy() for point in points]
        score_points(RuleConfig(name='ownership', query='fixture'), 'fixture', {}, points)
        self.assertEqual([vars(point) for point in points], before)

    def test_borrowed_normalized_input_and_fallback_equal_reference(self):
        from copy import deepcopy
        points = [build_raw_point(float(i), 100. + i) for i in range(10)]
        self.assertIs(_scoring_points(points), points)
        variants = [points, list(reversed(points)), points + [points[-1]]]
        for field, value in [('time', float('nan')), ('value', float('inf')),
                             ('bucket_start', float('nan')), ('bucket_end', float('inf')),
                             ('min_value', float('nan')), ('max_value', float('inf')),
                             ('sample_count', 0), ('sample_count', 2.5), ('sample_count', None)]:
            changed = deepcopy(points)
            setattr(changed[5], field, value)
            variants.append(changed)
        for variant in variants:
            expected = dedupe_consecutive_points(sorted(_valid_raw_points(variant), key=lambda p: p.time), owned=True)
            self.assertEqual(_scoring_points(variant), expected)
        before = deepcopy(points)
        score_points(RuleConfig(name='borrowed', query='fixture'), 'fixture', {}, points)
        self.assertEqual(points, before)


if __name__ == '__main__':
    unittest.main()
