from copy import deepcopy
from dataclasses import asdict
import math
import random
import unittest

from app.algorithms import evaluate_series
from app.canonical import build_raw_point, score_points
from app.guarded_rolling import GuardedRollingState
from app.guarded_ewma import GuardedEwmaState
from app.guarded_seasonal import GuardedSeasonalState
from app.models import RuleConfig, SeriesState


class GuardedRollingTests(unittest.TestCase):
    def test_new_references_preserve_flat_baseline_spread_floor(self):
        for state in (GuardedEwmaState(30, 4), GuardedSeasonalState(24, 8, 4)):
            for _ in range(200):
                state.update(100.)
            result = state.update(100.01)
            self.assertLess(max(result[2:]), 4)

    def test_seasonal_ring_bounds_and_invalid_input(self):
        large = GuardedSeasonalState(96, 10_000_000, 4)
        large.update(100.)
        self.assertEqual(len(large.offsets), 0, 'configuration must not eagerly allocate unobserved cycles')
        for period, depth in ((2, 3), (24, 8), (96, 12)):
            state = GuardedSeasonalState(period, depth, 4)
            with self.assertRaises(ValueError):
                state.update(float('nan'))
            self.assertEqual(state.count, 0)
            for i in range(5000):
                self.assertEqual(state.update(100+math.sin(i)) is None, i < 2*period)
            self.assertLessEqual(len(state.clean), depth*period+1)
            self.assertLessEqual(len(state.errors), 128)
            self.assertLessEqual(len(state.raw_errors), 138)
            self.assertLessEqual(len(state.biases), 16)
            self.assertLessEqual(len(state.recent), 10)
            self.assertEqual(state, deepcopy(state))

    def test_replay_stream_all_fields_direction_and_lifecycle(self):
        rng=random.Random(454097)
        values=[100+math.sin(i/15)*4+rng.gauss(0,.8) for i in range(1800)]
        values[700:760]=[v+20 for v in values[700:760]]
        values[1100:1160]=[v-20 for v in values[1100:1160]]
        for algorithm in ('zscore','mad','ewma','seasonal','level_shift'):
            for direction in ('high_or_low','high_mean','low_mean'):
                rule=RuleConfig(name='rolling',query='fixture',algorithm=algorithm,threshold=4,
                                seasonality_samples=round(2*math.pi*15) if algorithm == 'seasonal' else 144,
                                anomaly_direction=direction,persistence_buckets=3,persistence_window=4,
                                recovery_buckets=2,recovery_threshold=3,cooldown_buckets=2)
                points=[build_raw_point(i*60.,v) for i,v in enumerate(values)]
                batch=score_points(rule,'fixture',{},points)
                self.assertEqual(score_points(rule,'fixture',{},points[:1000]),batch[:1000])
                state=SeriesState.create(rule.history_limit,rule.baseline_window)
                for i,value in enumerate(values):
                    actual=evaluate_series(state,rule,'fixture',{},value,i*60.)
                    for key,expected in asdict(batch[i]).items():
                        if isinstance(expected,float):self.assertAlmostEqual(getattr(actual,key),expected,places=7,msg=f'{algorithm}/{direction}/{i}/{key}')
                        else:self.assertEqual(getattr(actual,key),expected,f'{algorithm}/{direction}/{i}/{key}')
                self.assertGreater(sum(p.is_anomaly for p in batch),0, f'{algorithm}/{direction}')
                before=deepcopy(state)
                evaluate_series(state,rule,'fixture',{},999.,(len(values)-1)*60.)
                self.assertEqual(state,before)

    def test_ewma_bounded_state_and_nonfinite_samples(self):
        state = GuardedEwmaState(30, 4.5)
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(ValueError):
                state.update(value)
            self.assertEqual(state.count, 0)
        for i in range(10000):
            self.assertEqual(state.update(100 + math.sin(i)) is None, i < 30)
        for name, limit in [('errors', 128), ('raw_errors', 138), ('recent', 10)]:
            self.assertLessEqual(len(getattr(state, name)), limit)
        self.assertEqual(state, deepcopy(state))

    def test_memory_invalid_samples_and_warmup(self):
        for algorithm in ('zscore','mad'):
            state=GuardedRollingState(algorithm,12,4)
            for value in (float('nan'),float('inf'),-float('inf')):
                with self.assertRaises(ValueError):state.update(value)
                self.assertEqual(state.count,0)
            for i in range(10000):self.assertEqual(state.update(100+math.sin(i)) is None,i<12)
            for name,limit in [('clean',12),('raw',128),('errors',128),('recent',10)]:
                self.assertLessEqual(len(getattr(state,name)),limit)
            self.assertEqual(state,deepcopy(state))

    def test_flat_and_quantized_baselines_keep_large_repeated_events(self):
        for algorithm in ('zscore','mad'):
            for amplitude in (0.,1.):
                state=GuardedRollingState(algorithm,12,4)
                for i in range(48):state.update(100+(i%2)*amplitude)
                for _ in range(3):
                    result=state.update(180.)
                    self.assertGreaterEqual(max(result[2:]),4)
