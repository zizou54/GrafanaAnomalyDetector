"""Causal rolling reference with guarded updates and bounded residual history."""
from __future__ import annotations

import math
from collections import deque
from statistics import median

from .harmonic import _correlation, _window_scale


def _std(values):
    center = sum(values) / len(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / len(values))


class GuardedRollingState:
    __slots__ = ('algorithm', 'window', 'threshold', 'count', 'clean', 'raw', 'errors',
                 'recent', 'frozen', 'noise', 'window_key', 'window_scale')

    def __init__(self, algorithm, window, threshold):
        if algorithm not in ('zscore', 'mad') or not isinstance(window, int) or window < 3 or not math.isfinite(threshold) or threshold <= 0:
            raise ValueError('A rolling model, window >=3 and positive finite threshold are required.')
        self.algorithm, self.window, self.threshold = algorithm, window, threshold
        self.count = 0
        self.clean = deque(maxlen=window)
        self.raw = deque(maxlen=128)
        self.errors = deque(maxlen=128)
        self.recent = deque(maxlen=10)
        self.frozen = None
        self.noise = None
        self.window_key = None
        self.window_scale = 1.

    def __eq__(self, other):
        if not isinstance(other, GuardedRollingState):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)

    def update(self, value):
        if not math.isfinite(value):
            raise ValueError('Rolling samples must be finite.')
        i = self.count
        self.count += 1
        history = list(self.clean)
        if len(history) < self.window:
            self.clean.append(value)
            self.raw.append(value)
            return None
        expected = sum(history) / len(history) if self.algorithm == 'zscore' else median(history)
        if self.frozen is None and (self.noise is None or i % 16 == 0):
            reference = list(self.errors) if len(self.errors) >= 32 else history
            ordered = sorted(reference)
            mid = len(ordered) // 2
            center = ordered[mid] if len(ordered) % 2 else (ordered[mid-1] + ordered[mid]) / 2
            spread = max(median([abs(v - center) for v in reference]) * 1.4826,
                         (ordered[int((len(ordered)-1)*.9)] - ordered[int((len(ordered)-1)*.1)]) / 2.563)
            if spread <= 1e-9:
                spread = max(abs(expected)*.02, 1e-6)
            context = list(self.raw)[:-10]
            rho = _correlation(context, sum(context)/len(context)) if context else 0.
            inflation = min(2.5, 1/math.sqrt(1-_correlation(reference, center)))
            self.noise = spread, rho, inflation
        spread, rho, inflation = self.noise
        if self.frozen is None:
            if self.algorithm == 'zscore':
                spread = max(spread, _std(history))
            else:
                spread = max(spread, median([abs(v - expected) for v in history]) * 1.4826)
                if len(set(history)) <= 5:
                    spread = max(spread, _std(history))
            spread *= inflation
        else:
            spread, rho = self.frozen
        residual = (value - expected) / spread
        self.recent.append(residual)
        average = sum(self.recent) / len(self.recent)
        key = len(self.recent), rho
        if key != self.window_key:
            self.window_key = key
            self.window_scale = _window_scale(*key)
        window_score = (abs(average) * self.window_scale
                        if residual*average > 0 and abs(residual) > max(1, abs(average)*.5) else 0.)
        score = max(abs(residual), window_score)
        # A fully constant baseline needs no long noise calibration before guarding.
        calibrated = (i >= max(128, 4*self.window) or min(history) == max(history)
                      or i >= 2*self.window and abs(residual) >= 2*self.threshold)
        if score >= min(3., .75*self.threshold) and calibrated:
            self.frozen = spread, rho
            self.clean.append(expected)
        else:
            self.frozen = None
            self.clean.append(value)
            self.errors.append(value-expected)
        self.raw.append(value)
        return expected, spread, abs(residual), window_score
