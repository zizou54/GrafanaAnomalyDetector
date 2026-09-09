"""Bounded, causal harmonic scorer shared by replay and streaming evaluation."""
from __future__ import annotations

import math
from collections import deque
from statistics import median


def _central_spread(ordered):
    def quantile(p):
        index = (len(ordered) - 1) * p
        low = int(index)
        return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (index - low)
    return (quantile(.9) - quantile(.1)) / 2.5631031310892007


def _correlation(values, center):
    variance = covariance = 0.
    previous = None
    for value in values:
        current = value - center
        variance += current * current
        if previous is not None:
            covariance += previous * current
        previous = current
    return max(0., min(.98, covariance / variance)) if variance else 0.


def _window_scale(count, rho):
    effective = count / (1 + 2 * sum((1 - k / count) * rho ** k for k in range(1, count)))
    return math.sqrt(effective)


class HarmonicState:
    def __init__(self, period: int, threshold: float):
        if not isinstance(period, int) or not 8 <= period <= 4096:
            raise ValueError('Harmonic period must be between 8 and 4096 scored samples.')
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError('Harmonic threshold must be positive and finite.')
        self.period, self.threshold = period, threshold
        self.noise_refresh = min(16, period)
        self.count = 0
        self.clean = deque(maxlen=2 * period)
        self.raw = deque(maxlen=min(2 * period, 138))
        self.errors = deque(maxlen=128)
        self.biases = deque(maxlen=32)
        self.normalized = deque(maxlen=10)
        self.sines = [math.sin(j * math.tau / period) for j in range(2 * period)]
        self.cosines = [math.cos(j * math.tau / period) for j in range(2 * period)]
        self.phase_sine, self.phase_cosine = math.sin(math.tau / period), math.cos(math.tau / period)
        self.total = self.sine_total = self.cosine_total = 0.
        self.noise = self.frozen = None
        self.window_key = None
        self.window_scale = 1.

    def _noise(self, expected, mean, sine, cosine):
        past = list(self.errors) if len(self.errors) >= 32 else [
            v - mean - sine * self.sines[j] - cosine * self.cosines[j] for j, v in enumerate(self.clean)]
        center = median(past)
        spread = max(median(abs(x - center) for x in past) * 1.4826, abs(expected) * 1e-6, 1e-6)
        rho = _correlation(past, center)
        # Exclude the emerging event from the broad noise/correlation reference.
        offset = 2 * self.period - len(self.raw)
        raw_errors = [v - mean - sine * self.sines[offset + j] - cosine * self.cosines[offset + j]
                      for j, v in enumerate(list(self.raw)[:-10])]
        ordered = sorted(raw_errors)
        middle = len(ordered) // 2
        center = ordered[middle] if len(ordered) % 2 else (ordered[middle-1] + ordered[middle]) / 2
        spread = max(spread, median([abs(x - center) for x in raw_errors]) * 1.4826, _central_spread(ordered))
        rho = max(rho, _correlation(raw_errors, center))
        # A fitted baseline understates uncertainty on strongly correlated noise.
        # Bound the inflation so this safeguard cannot erase clear point events.
        return spread * min(2.5, 1 / math.sqrt(1 - rho)), rho

    def update(self, value: float):
        if not math.isfinite(value):
            raise ValueError('Harmonic samples must be finite.')
        i, n = self.count, 2 * self.period
        self.count += 1
        if i < n:
            self.clean.append(value)
            self.raw.append(value)
            return None
        if i % self.period == 0:
            self.total = sum(self.clean)
            self.sine_total = sum(v * self.sines[j] for j, v in enumerate(self.clean))
            self.cosine_total = sum(v * self.cosines[j] for j, v in enumerate(self.clean))
        mean, sine, cosine = self.total / n, 2 * self.sine_total / n, 2 * self.cosine_total / n
        base = mean + cosine
        expected = base + (median(self.biases) if self.biases else 0.)
        if self.frozen is None and (self.noise is None or i % self.noise_refresh == 0):
            self.noise = self._noise(expected, mean, sine, cosine)
        spread, rho = self.frozen if self.frozen is not None else self.noise
        residual = (value - expected) / spread
        self.normalized.append(residual)
        count = len(self.normalized)
        average = sum(self.normalized) / count
        # Noise is held between refreshes; reuse only the identical (count, rho).
        key = count, rho
        if key != self.window_key:
            self.window_scale = _window_scale(count, rho)
            self.window_key = key
        window = abs(average) * self.window_scale if average * residual > 0 and abs(residual) > 1 else 0.
        point = abs(residual)
        if max(point, window) >= self.threshold * .75:
            self.frozen = spread, rho
            new = base
        else:
            self.frozen = None
            new = value
            self.biases.append(value - base)
            self.errors.append(value - expected)
        old = self.clean[0]
        self.clean.append(new)
        self.raw.append(value)
        self.total += new - old
        old_sine = self.sine_total
        corrected_cosine = self.cosine_total - old + new
        self.sine_total = old_sine * self.phase_cosine - corrected_cosine * self.phase_sine
        self.cosine_total = corrected_cosine * self.phase_cosine + old_sine * self.phase_sine
        return expected, spread, point, window
