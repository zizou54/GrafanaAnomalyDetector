import { correlation, HarmonicResult, median, Ring, sum } from './harmonic';

const standardDeviation = (values: number[]) => {
  const center = sum(values) / values.length;
  return Math.sqrt(sum(values.map((v) => (v - center) ** 2)) / values.length);
};

export class GuardedRollingState {
  private count = 0;
  private clean: Ring;
  private raw = new Ring(128);
  private errors = new Ring(128);
  private recent = new Ring(10);
  private frozen: [number, number] | null = null;
  private noise: [number, number, number] | null = null;
  private windowCount = 0;
  private windowRho = -1;
  private windowScale = 1;

  constructor(private algorithm: 'zscore' | 'mad', private window: number, private threshold: number) {
    if (!Number.isInteger(window) || window < 3 || !Number.isFinite(threshold) || threshold <= 0) {
      throw new Error('Rolling window must be an integer >=3 and threshold positive and finite.');
    }
    this.clean = new Ring(window);
  }

  update(value: number): HarmonicResult | null {
    if (!Number.isFinite(value)) { throw new Error('Rolling samples must be finite.'); }
    const i = this.count++;
    const history = this.clean.values();
    if (history.length < this.window) { this.clean.push(value); this.raw.push(value); return null; }
    const expected = this.algorithm === 'zscore' ? sum(history) / history.length : median(history);
    if (this.frozen === null && (this.noise === null || i % 16 === 0)) {
      const reference = this.errors.length >= 32 ? this.errors.values() : history;
      const center = median(reference);
      const ordered = [...reference].sort((a, b) => a - b);
      let spread = Math.max(median(reference.map((v) => Math.abs(v - center))) * 1.4826,
        (ordered[Math.floor((ordered.length - 1) * .9)] - ordered[Math.floor((ordered.length - 1) * .1)]) / 2.563);
      if (spread <= 1e-9) { spread = Math.max(Math.abs(expected) * .02, 1e-6); }
      const context = this.raw.values().slice(0, -10);
      const rho = context.length ? correlation(context, sum(context) / context.length) : 0;
      this.noise = [spread, rho, Math.min(2.5, 1 / Math.sqrt(1 - correlation(reference, center)))];
    }
    let [spread, rho, inflation] = this.noise!;
    if (this.frozen === null) {
      if (this.algorithm === 'zscore') { spread = Math.max(spread, standardDeviation(history)); }
      else {
        spread = Math.max(spread, median(history.map((v) => Math.abs(v - expected))) * 1.4826);
        if (new Set(history).size <= 5) { spread = Math.max(spread, standardDeviation(history)); }
      }
      spread *= inflation;
    } else {
      [spread, rho] = this.frozen;
    }
    const residual = (value - expected) / spread;
    this.recent.push(residual);
    const count = this.recent.length;
    const average = sum(this.recent.values()) / count;
    if (count !== this.windowCount || rho !== this.windowRho) {
      let adjustment = 0;
      for (let k = 1; k < count; k++) { adjustment += (1 - k / count) * rho ** k; }
      this.windowScale = Math.sqrt(count / (1 + 2 * adjustment));
      this.windowCount = count;
      this.windowRho = rho;
    }
    const windowScore = residual * average > 0 && Math.abs(residual) > Math.max(1, Math.abs(average) * .5)
      ? Math.abs(average) * this.windowScale : 0;
    const pointScore = Math.abs(residual);
    const calibrated = i >= Math.max(128, 4 * this.window) || Math.min(...history) === Math.max(...history)
      || (i >= 2 * this.window && pointScore >= 2 * this.threshold);
    if (Math.max(pointScore, windowScore) >= Math.min(3, .75 * this.threshold) && calibrated) {
      this.frozen = [spread, rho]; this.clean.push(expected);
    } else {
      this.frozen = null; this.clean.push(value); this.errors.push(value - expected);
    }
    this.raw.push(value);
    return { expected, spread, pointScore, windowScore };
  }
}
