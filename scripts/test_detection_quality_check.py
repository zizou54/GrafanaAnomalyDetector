import unittest

from detection_quality_check import PROFILES, throughput_failures


class ThroughputGateTests(unittest.TestCase):
    def results(self):
        return {scenario: {model: {'points_per_second': 10_000} for model in PROFILES}
                for scenario in ('clear', 'hard')}

    def test_exact_boundary_passes_for_every_model_and_scenario(self):
        self.assertEqual(throughput_failures(self.results()), [])

    def test_each_scenario_and_model_is_checked_independently(self):
        for scenario in ('clear', 'hard'):
            for model in PROFILES:
                with self.subTest(scenario=scenario, model=model):
                    results = self.results()
                    results[scenario][model]['points_per_second'] = 9_999
                    self.assertEqual(throughput_failures(results), [
                        f'{scenario}/{model}: scorer throughput below 10k points/s'])

    def test_invalid_measurements_cannot_pass(self):
        for invalid in (float('nan'), float('inf'), -1):
            with self.subTest(invalid=invalid):
                results = self.results()
                results['hard']['harmonic']['points_per_second'] = invalid
                self.assertEqual(len(throughput_failures(results)), 1)


if __name__ == '__main__':
    unittest.main()
