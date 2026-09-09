// Keep this kernel aligned with exporter/app/harmonic.py (no Grafana dependencies).
export const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);
export const median = (values: number[]) => {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
};
const centralSpread = (values: number[]) => {
  const ordered = [...values].sort((a, b) => a - b);
  const quantile = (p: number) => {
    const index = (ordered.length - 1) * p;
    const low = Math.floor(index);
    return ordered[low] + (ordered[Math.min(low + 1, ordered.length - 1)] - ordered[low]) * (index - low);
  };
  return (quantile(.9) - quantile(.1)) / 2.5631031310892007;
};
export const correlation = (values: number[], center: number) => {
  const centered = values.map((v) => v - center);
  const variance = sum(centered.map((v) => v * v));
  let covariance = 0;
  for (let i = 1; i < centered.length; i++) { covariance += centered[i - 1] * centered[i]; }
  return variance ? Math.max(0, Math.min(.98, covariance / variance)) : 0;
};

export class Ring {
  private items: number[] = [];
  private start = 0;
  constructor(private capacity: number) {}
  get length() { return this.items.length; }
  get first() { return this.items[this.start]; }
  push(value: number) {
    if (this.items.length < this.capacity) { this.items.push(value); }
    else { this.items[this.start] = value; this.start = (this.start + 1) % this.capacity; }
  }
  values() { return this.items.slice(this.start).concat(this.items.slice(0, this.start)); }
}

export interface HarmonicResult { expected: number; spread: number; pointScore: number; windowScore: number; }

export class HarmonicState {
  private count = 0;
  private clean: Ring;
  private raw: Ring;
  private errors = new Ring(128);
  private biases = new Ring(32);
  private normalized = new Ring(10);
  private sines: number[];
  private cosines: number[];
  private phaseSine: number;
  private phaseCosine: number;
  private total = 0;
  private sineTotal = 0;
  private cosineTotal = 0;
  private noise: [number, number] | null = null;
  private frozen: [number, number] | null = null;
  private windowCount = 0;
  private windowRho = -1;
  private windowScale = 1;

  constructor(private period: number, private threshold: number) {
    if (!Number.isInteger(period) || period < 8 || period > 4096) { throw new Error('Harmonic period must be 8 to 4096 scored samples.'); }
    if (!Number.isFinite(threshold) || threshold <= 0) { throw new Error('Harmonic threshold must be positive and finite.'); }
    this.clean = new Ring(2 * period);
    this.raw = new Ring(Math.min(2 * period, 138));
    this.sines = Array.from({ length: 2 * period }, (_, j) => Math.sin(j * (2 * Math.PI) / period));
    this.cosines = Array.from({ length: 2 * period }, (_, j) => Math.cos(j * (2 * Math.PI) / period));
    this.phaseSine = Math.sin(2 * Math.PI / period);
    this.phaseCosine = Math.cos(2 * Math.PI / period);
  }

  private estimateNoise(expected: number, mean: number, sine: number, cosine: number): [number, number] {
    const past = this.errors.length >= 32 ? this.errors.values() : this.clean.values().map((v, j) => v - mean - sine * this.sines[j] - cosine * this.cosines[j]);
    const center = median(past);
    let spread = Math.max(median(past.map((x) => Math.abs(x - center))) * 1.4826, Math.abs(expected) * 1e-6, 1e-6);
    const rho = correlation(past, center);
    const offset = 2 * this.period - this.raw.length;
    const rawErrors = this.raw.values().slice(0, -10).map((v, j) => v - mean - sine * this.sines[offset + j] - cosine * this.cosines[offset + j]);
    const rawCenter = median(rawErrors);
    spread = Math.max(spread, median(rawErrors.map((x) => Math.abs(x - rawCenter))) * 1.4826, centralSpread(rawErrors));
    const effectiveRho = Math.max(rho, correlation(rawErrors, rawCenter));
    return [spread * Math.min(2.5, 1 / Math.sqrt(1 - effectiveRho)), effectiveRho];
  }

  update(value: number): HarmonicResult | null {
    if (!Number.isFinite(value)) { throw new Error('Harmonic samples must be finite.'); }
    const i = this.count++;
    const n = 2 * this.period;
    if (i < n) { this.clean.push(value); this.raw.push(value); return null; }
    if (i % this.period === 0) {
      const history = this.clean.values();
      this.total = sum(history);
      this.sineTotal = sum(history.map((v, j) => v * this.sines[j]));
      this.cosineTotal = sum(history.map((v, j) => v * this.cosines[j]));
    }
    const mean = this.total / n, sine = 2 * this.sineTotal / n, cosine = 2 * this.cosineTotal / n;
    const base = mean + cosine;
    const expected = base + (this.biases.length ? median(this.biases.values()) : 0);
    if (this.frozen === null && (this.noise === null || i % Math.min(16, this.period) === 0)) { this.noise = this.estimateNoise(expected, mean, sine, cosine); }
    const [spread, rho] = (this.frozen ?? this.noise)!;
    const residual = (value - expected) / spread;
    this.normalized.push(residual);
    const count = this.normalized.length;
    const average = sum(this.normalized.values()) / count;
    // Reuse only an identical noise correlation and window length.
    if (count !== this.windowCount || rho !== this.windowRho) {
      let adjustment = 0;
      for (let k = 1; k < count; k++) { adjustment += (1 - k / count) * rho ** k; }
      this.windowScale = Math.sqrt(count / (1 + 2 * adjustment));
      this.windowCount = count;
      this.windowRho = rho;
    }
    const windowScore = average * residual > 0 && Math.abs(residual) > 1 ? Math.abs(average) * this.windowScale : 0;
    const pointScore = Math.abs(residual);
    let next: number;
    if (Math.max(pointScore, windowScore) >= this.threshold * .75) { this.frozen = [spread, rho]; next = base; }
    else { this.frozen = null; next = value; this.biases.push(value - base); this.errors.push(value - expected); }
    const old = this.clean.first;
    this.clean.push(next);
    this.raw.push(value);
    this.total += next - old;
    const oldSine = this.sineTotal, correctedCosine = this.cosineTotal - old + next;
    this.sineTotal = oldSine * this.phaseCosine - correctedCosine * this.phaseSine;
    this.cosineTotal = correctedCosine * this.phaseCosine + oldSine * this.phaseSine;
    return { expected, spread, pointScore, windowScore };
  }
}
