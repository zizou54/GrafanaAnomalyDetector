"""Bounded causal double exponential reference with damped guarded trend."""
import math
from collections import deque
from statistics import median

from .harmonic import _correlation, _window_scale


class GuardedEwmaState:
    def __init__(self, window, threshold, evidence_window=10):
        if not isinstance(window, int) or window < 3 or not math.isfinite(threshold) or threshold <= 0:
            raise ValueError('EWMA requires window >=3 and a finite positive threshold.')
        self.window, self.threshold = window, threshold
        self.alpha = 2 / (window + 1)
        self.count = 0
        self.smooth = self.smooth2 = None
        self.errors = deque(maxlen=128)
        self.raw_errors = deque(maxlen=138)
        if not isinstance(evidence_window, int) or not 3 <= evidence_window <= 12:
            raise ValueError('Evidence window must be between 3 and 12.')
        self.recent = deque(maxlen=evidence_window)
        self.noise = self.frozen = None
        self.window_key = None
        self.window_scale = 1.

    def __eq__(self, other):
        return isinstance(other, GuardedEwmaState) and self.__dict__ == other.__dict__

    def update(self, value):
        if not math.isfinite(value):
            raise ValueError('EWMA samples must be finite.')
        i = self.count
        self.count += 1
        if self.smooth is None:
            self.smooth = self.smooth2 = value
        expected = 2*self.smooth - self.smooth2
        error = value - expected
        if i < self.window:
            self.errors.append(error)
            self.raw_errors.append(error)
            self.smooth = self.alpha*value + (1-self.alpha)*self.smooth
            self.smooth2 = self.alpha*self.smooth + (1-self.alpha)*self.smooth2
            return None
        if self.frozen is None and (self.noise is None or i % 16 == 0):
            reference = list(self.errors)
            raw = list(self.raw_errors)[:-10] or reference
            center = median(reference)
            ordered = sorted(raw)
            spread = max(median(abs(x-center) for x in reference)*1.4826,
                         (ordered[int((len(ordered)-1)*.9)]-ordered[int((len(ordered)-1)*.1)])/2.563)
            if spread <= 1e-9:
                spread = max(abs(expected)*.02, 1e-6)*1.4826
            middle = len(ordered)//2
            raw_center = ordered[middle] if len(ordered) % 2 else (ordered[middle-1]+ordered[middle])/2
            rho = max(_correlation(reference, center), _correlation(raw, raw_center))
            self.noise = spread*min(2.5, 1/math.sqrt(1-rho)), rho
        spread, rho = self.frozen or self.noise
        residual = error/spread
        self.recent.append(residual)
        average = sum(self.recent)/len(self.recent)
        key = len(self.recent), rho
        if key != self.window_key:
            self.window_key = key
            self.window_scale = _window_scale(*key)
        window_score = (abs(average)*self.window_scale
                        if residual*average > 0 and abs(residual) > max(1, abs(average)*.5) else 0.)
        # Keep point evidence in the legacy median-absolute-residual units.
        point_scale = spread/min(2.5, 1/math.sqrt(1-rho))
        point_spread = point_scale/1.4826
        point_score = abs(error)/point_scale*1.4826
        calibrated = (i >= max(128, 4*self.window) or all(abs(x) <= 1e-9 for x in self.errors)
                      or i >= 2*self.window and point_score >= 2*self.threshold)
        guard = calibrated and max(abs(residual), window_score) >= min(3, .75*self.threshold)
        self.raw_errors.append(error)
        if guard:
            self.frozen = spread, rho
        else:
            self.frozen = None
            self.errors.append(error)
            self.smooth = self.alpha*value + (1-self.alpha)*self.smooth
        # Trend decays even during guarding; freezing it caused post-event FP.
        self.smooth2 = self.alpha*self.smooth + (1-self.alpha)*self.smooth2
        return expected, point_spread, point_score, window_score
