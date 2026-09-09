"""Bounded causal phase reference; calendar refinements use their existing path."""
import math
from collections import deque
from statistics import median
from .harmonic import _correlation, _window_scale


class GuardedSeasonalState:
    def __init__(self, period, depth, threshold):
        if not isinstance(period, int) or period < 2 or not isinstance(depth, int) or depth < 3:
            raise ValueError('Seasonal period >=2 and depth >=3 are required.')
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError('A finite positive threshold is required.')
        self.period, self.depth, self.threshold = period, depth, threshold
        self.capacity = depth*period + 1
        self.offsets = []
        self.clean = []
        self.count = 0
        self.errors = deque(maxlen=128)
        self.raw_errors = deque(maxlen=138)
        self.recent = deque(maxlen=10)
        self.biases = deque(maxlen=16)
        self.drift = 0.
        self.noise = self.frozen = None
        self.window_key = None
        self.window_scale = 1.

    def __eq__(self, other):
        return isinstance(other, GuardedSeasonalState) and self.__dict__ == other.__dict__

    def _append(self, value, index):
        if len(self.clean) < self.capacity:
            self.clean.append(value)
        else:
            self.clean[index % self.capacity] = value

    def update(self, value):
        if not math.isfinite(value):
            raise ValueError('Seasonal samples must be finite.')
        i = self.count
        self.count += 1
        period, capacity = self.period, self.capacity
        if self.frozen is None and i >= 2*period and i % 16 == 0:
            differences = [self.clean[j % capacity]-self.clean[(j-period) % capacity]
                           for j in range(i-period, i)]
            change = median(differences)
            rho = _correlation(differences, change)
            uncertainty = median(abs(v-change) for v in differences)*1.4826/math.sqrt(1-rho)
            drift = change/period if rho < .5 and abs(change) > 2*max(uncertainty, 1e-6) else 0.
            if drift != self.drift:
                self.biases.clear()
            self.drift = drift
        clean, drift = self.clean, self.drift
        peer_cycles = min(self.depth, i//period)
        if len(self.offsets) < 3*peer_cycles:
            self.offsets.extend(offset for k in range(len(self.offsets)//3+1, peer_cycles+1)
                                for offset in (-k*period-1, -k*period, -k*period+1))
        offsets = self.offsets
        # Most series have no confirmed linear drift; skip discarded arithmetic.
        peers = ([clean[(i+offset) % capacity]-drift*offset for offset in offsets if i+offset >= 0]
                 if drift else [clean[(i+offset) % capacity] for offset in offsets if i+offset >= 0])
        base = sum(peers)/len(peers) if peers else value
        expected = base + (median(self.biases) if self.biases else 0.)
        error = value-expected
        if i < 2*period:
            self._append(value, i)
            self.errors.append(error)
            self.raw_errors.append(error)
            return None
        if self.frozen is None and (self.noise is None or i % 16 == 0):
            reference = list(self.errors)
            raw = list(self.raw_errors)[:-10] or reference
            center = median(reference)
            ordered = sorted(raw)
            spread = max(median(abs(x-center) for x in reference)*1.4826,
                         (ordered[int((len(ordered)-1)*.9)]-ordered[int((len(ordered)-1)*.1)])/2.563)
            if spread <= 1e-9:
                spread = max(abs(expected)*.02, 1e-6)
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
        guard = i >= max(128, 4*self.depth) and max(abs(residual), window_score) >= min(3, .75*self.threshold)
        self.raw_errors.append(error)
        if guard:
            self.frozen = spread, rho
            accepted = base
        else:
            self.frozen = None
            accepted = value
            self.errors.append(error)
            self.biases.append(value-base)
        self._append(accepted, i)
        return expected, spread, abs(residual), window_score
