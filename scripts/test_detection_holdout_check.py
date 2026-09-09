import unittest

from detection_holdout_check import EVALUATE_FROM, SHIFT, SPIKES, fixture, summarize


class HoldoutMeasurementTests(unittest.TestCase):
    def test_seeds_are_reproducible_and_not_identical(self):
        self.assertEqual(fixture(7, 'stationary', False), fixture(7, 'stationary', False))
        self.assertNotEqual(fixture(7, 'stationary', False), fixture(19, 'stationary', False))

    def test_injection_changes_only_the_declared_ground_truth_after_warmup(self):
        baseline = fixture(73, 'seasonal', False)
        injected = fixture(73, 'seasonal', True)
        changed = {index for index, (left, right) in enumerate(zip(baseline, injected)) if left.value != right.value}
        self.assertEqual(changed, set(SPIKES).union(SHIFT))
        self.assertGreater(min(changed), EVALUATE_FROM)

    def test_zero_predictions_are_not_reported_as_perfect_precision(self):
        result = summarize([{'injected': True, 'metrics': {
            'tp': 0, 'fp': 0, 'fn': 42, 'background': 598, 'spike_hits': 0,
            'shift_detected': 0, 'shift_delay': None, 'high_confidence_fp': 0, 'unscored': 0}}])
        self.assertIsNone(result['point_precision'])
        self.assertEqual(result['point_recall'], 0)
        self.assertEqual(result['spike_recall'], 0)
        self.assertEqual(result['shift_recall'], 0)


if __name__ == '__main__':
    unittest.main()
