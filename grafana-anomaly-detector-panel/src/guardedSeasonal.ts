import { correlation, HarmonicResult, median, Ring, sum } from './harmonic';

export class GuardedSeasonalState {
  private count = 0;
  private capacity: number;
  private clean: number[] = [];
  private errors = new Ring(128);
  private rawErrors = new Ring(138);
  private recent = new Ring(10);
  private biases = new Ring(16);
  private drift = 0;
  private noise: [number, number] | null = null;
  private frozen: [number, number] | null = null;
  private windowCount = 0;
  private windowRho = -1;
  private windowScale = 1;

  constructor(private period: number, private depth: number, private threshold: number) {
    if (!Number.isInteger(period) || period < 2 || !Number.isInteger(depth) || depth < 3 || !Number.isFinite(threshold) || threshold <= 0) {
      throw new Error('Seasonal period >=2, depth >=3 and a finite positive threshold are required.');
    }
    this.capacity = depth * period + 1;
  }

  private append(value: number, index: number) {
    if (this.clean.length < this.capacity) { this.clean.push(value); }
    else { this.clean[index % this.capacity] = value; }
  }

  update(value: number): HarmonicResult | null {
    if (!Number.isFinite(value)) { throw new Error('Seasonal samples must be finite.'); }
    const i = this.count++;
    if (this.frozen === null && i >= 2 * this.period && i % 16 === 0) {
      const differences: number[] = [];
      for (let j = i - this.period; j < i; j++) {
        differences.push(this.clean[j % this.capacity] - this.clean[(j - this.period) % this.capacity]);
      }
      const change = median(differences);
      const rho = correlation(differences, change);
      const uncertainty = median(differences.map((v) => Math.abs(v - change))) * 1.4826 / Math.sqrt(1 - rho);
      const drift = rho < .5 && Math.abs(change) > 2 * Math.max(uncertainty, 1e-6) ? change / this.period : 0;
      if (drift !== this.drift) { this.biases = new Ring(16); }
      this.drift = drift;
    }
    const peers: number[] = [];
    for (let k = 1; k <= Math.min(this.depth, Math.floor(i / this.period)); k++) {
      for (const j of [i - k * this.period - 1, i - k * this.period, i - k * this.period + 1]) {
        if (j >= 0 && j < i) { peers.push(this.clean[j % this.capacity] + this.drift * (i - j)); }
      }
    }
    const base = peers.length ? sum(peers) / peers.length : value;
    const expected = base + (this.biases.length ? median(this.biases.values()) : 0);
    const error = value - expected;
    if (i < 2 * this.period) {
      this.append(value, i); this.errors.push(error); this.rawErrors.push(error);
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
      if (spread <= 1e-9) { spread = Math.max(Math.abs(expected) * .02, 1e-6); }
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
    const guard = i >= Math.max(128, 4 * this.depth) && Math.max(Math.abs(residual), windowScore) >= Math.min(3, .75 * this.threshold);
    this.rawErrors.push(error);
    let accepted: number;
    if (guard) { this.frozen = [spread, rho]; accepted = base; }
    else {
      this.frozen = null; accepted = value;
      this.errors.push(error); this.biases.push(value - base);
    }
    this.append(accepted, i);
    return { expected, spread, pointScore: Math.abs(residual), windowScore };
  }
}
