import { correlation, HarmonicResult, median, Ring, sum } from './harmonic';

export class GuardedEwmaState {
  private count = 0;
  private smooth: number | null = null;
  private smooth2 = 0;
  private errors = new Ring(128);
  private rawErrors = new Ring(138);
  private recent: Ring;
  private noise: [number, number] | null = null;
  private frozen: [number, number] | null = null;
  private windowCount = 0;
  private windowRho = -1;
  private windowScale = 1;
  private alpha: number;

  constructor(private window: number, private threshold: number, evidenceWindow = 10) {
    if (!Number.isInteger(window) || window < 3 || !Number.isFinite(threshold) || threshold <= 0) {
      throw new Error('EWMA requires window >=3 and a finite positive threshold.');
    }
    this.alpha = 2 / (window + 1);
    if (!Number.isInteger(evidenceWindow) || evidenceWindow < 3 || evidenceWindow > 12) {
      throw new Error('Evidence window must be between 3 and 12.');
    }
    this.recent = new Ring(evidenceWindow);
  }

  update(value: number): HarmonicResult | null {
    if (!Number.isFinite(value)) { throw new Error('EWMA samples must be finite.'); }
    const i = this.count++;
    if (this.smooth === null) { this.smooth = this.smooth2 = value; }
    const expected = 2 * this.smooth - this.smooth2;
    const error = value - expected;
    if (i < this.window) {
      this.errors.push(error); this.rawErrors.push(error);
      this.smooth = this.alpha * value + (1 - this.alpha) * this.smooth;
      this.smooth2 = this.alpha * this.smooth + (1 - this.alpha) * this.smooth2;
      return null;
    }
    if (this.frozen === null && (this.noise === null || i % 16 === 0)) {
      const reference = this.errors.values();
      let raw = this.rawErrors.values().slice(0, -10);
      if (!raw.length) { raw = reference; }
      const center = median(reference);
      const ordered = [...raw].sort((a, b) => a - b);
      let spread = Math.max(median(reference.map((x) => Math.abs(x - center))) * 1.4826,
        (ordered[Math.floor((ordered.length - 1) * .9)] - ordered[Math.floor((ordered.length - 1) * .1)]) / 2.563);
      if (spread <= 1e-9) { spread = Math.max(Math.abs(expected) * .02, 1e-6) * 1.4826; }
      const rho = Math.max(correlation(reference, center), correlation(raw, median(raw)));
      this.noise = [spread * Math.min(2.5, 1 / Math.sqrt(1 - rho)), rho];
    }
    const [spread, rho] = this.frozen ?? this.noise!;
    const residual = error / spread;
    this.recent.push(residual);
    const count = this.recent.length;
    const average = sum(this.recent.values()) / count;
    if (count !== this.windowCount || rho !== this.windowRho) {
      let adjustment = 0;
      for (let k = 1; k < count; k++) { adjustment += (1 - k / count) * rho ** k; }
      this.windowScale = Math.sqrt(count / (1 + 2 * adjustment));
      this.windowCount = count; this.windowRho = rho;
    }
    const windowScore = residual * average > 0 && Math.abs(residual) > Math.max(1, Math.abs(average) * .5)
      ? Math.abs(average) * this.windowScale : 0;
    const inflation = Math.min(2.5, 1 / Math.sqrt(1 - rho));
    const pointSpread = spread / inflation / 1.4826;
    const pointScore = Math.abs(error) / (spread / inflation) * 1.4826;
    const calibrated = i >= Math.max(128, 4 * this.window) || this.errors.values().every((x) => Math.abs(x) <= 1e-9)
      || (i >= 2 * this.window && pointScore >= 2 * this.threshold);
    const guard = calibrated && Math.max(Math.abs(residual), windowScore) >= Math.min(3, .75 * this.threshold);
    this.rawErrors.push(error);
    if (guard) { this.frozen = [spread, rho]; }
    else {
      this.frozen = null; this.errors.push(error);
      this.smooth = this.alpha * value + (1 - this.alpha) * this.smooth;
    }
    this.smooth2 = this.alpha * this.smooth + (1 - this.alpha) * this.smooth2;
    return { expected, spread: pointSpread, pointScore, windowScore };
  }
}
