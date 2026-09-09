import { analyzePoints, buildRawPoint, getWarmupHistoryPoints, MAX_RAW_SCORE, resolveValueDomain, ScoringOptions } from './scoring';

const buildBoundaryScenario = () =>
  [100, 100.2, 99.8, 106, 100.1, 99.9, 100.3, 99.7, 100.2, 99.8, 100.1, 99.9, 130].map((value, index) =>
    buildRawPoint(index * 60_000, value)
  );

const baseOptions: ScoringOptions = {
  algorithm: 'zscore',
  sensitivity: 4,
  baselineWindow: 12,
  seasonalitySamples: 24,
  seasonalRefinement: 'cycle',
  severityPreset: 'balanced',
};

describe('canonical anomaly scoring', () => {
  it('harmonic is causal, warms for two cycles and retains direction policy', () => {
    const points = Array.from({ length: 700 }, (_, i) => buildRawPoint(i * 60_000,
      100 + 4 * Math.sin(i * 2 * Math.PI / 24) + Math.sin(i * 7) * .8 + (i >= 500 && i < 550 ? 20 : 0)));
    const options: ScoringOptions = { ...baseOptions, algorithm: 'harmonic', seasonalitySamples: 24 };
    const full = analyzePoints(points, options);
    expect(full.slice(0, 48).every((p) => p.expected === null && !p.isAnomaly)).toBe(true);
    expect(full[48].expected).not.toBeNull();
    expect(analyzePoints(points.slice(0, 530), options)).toEqual(full.slice(0, 530));
    expect(full.slice(500, 550).some((p) => p.isAnomaly)).toBe(true);
    expect(analyzePoints(points, { ...options, anomalyDirection: 'low_mean' }).slice(500, 550).every((p) => !p.isAnomaly)).toBe(true);
  });
  it.each([-1, 1])('seasonal cycle trend follows chronological peers (direction %s)', (direction) => {
    const points = Array.from({ length: 25 }, (_, i) => buildRawPoint(i * 60_000, 100 + direction * Math.floor(i / 4) * 2 + i % 4));
    const result = analyzePoints(points, { ...baseOptions, algorithm: 'seasonal', baselineWindow: 3, seasonalitySamples: 4 });
    expect(result[24].expected).toBe(100 + direction * 10);
  });

  it('does not label the return to baseline as another level shift', () => {
    const values = [...Array.from({ length: 60 }, (_, i) => 100 + (i % 2 ? 0.5 : -0.5)), ...Array(6).fill(130), 100];
    const result = analyzePoints(values.map((v, i) => buildRawPoint(i * 60_000, v)), { ...baseOptions, algorithm: 'level_shift', baselineWindow: 30 });
    expect(result[result.length - 2].isAnomaly).toBe(true);
    expect(result[result.length - 1].isAnomaly).toBe(false);
    expect(result[result.length - 1].windowScore).toBe(0);
  });

  it.each(['zscore', 'mad', 'ewma', 'seasonal', 'level_shift'] as const)(
    '%s decisions are causal and its quality gate blocks gap-driven spikes',
    (algorithm) => {
      const options = { ...baseOptions, algorithm, seasonalitySamples: 4 };
      const points = Array.from({ length: 100 }, (_, index) => buildRawPoint(index * 60_000, 100 + (index % 2)));
      const prefix = analyzePoints(points, options);
      const extended = [...points, buildRawPoint(100 * 60_000 + 3_600_000, 180)];
      expect(analyzePoints(extended, options).slice(0, points.length)).toEqual(prefix);
      const gated = analyzePoints(extended, { ...options, dataQualityGate: true });
      expect(gated[gated.length - 1]).toMatchObject({ dataQualityLabel: 'gappy', isAnomaly: false, severityScore: 0 });
      const regular = [...points, buildRawPoint(100 * 60_000, 180)];
      const valid = analyzePoints(regular, { ...options, dataQualityGate: true });
      expect(valid[valid.length - 1]).toMatchObject({ dataQualityLabel: 'healthy', isAnomaly: true });
    }
  );

  it('uses the configured history window as the range-boundary warm-up', () => {
    expect(getWarmupHistoryPoints(12)).toBe(12);
    expect(getWarmupHistoryPoints(1)).toBe(3);
    expect(getWarmupHistoryPoints(Number.NaN)).toBe(3);
  });

  it.each(['zscore', 'mad', 'ewma', 'level_shift'] as const)(
    'suppresses premature %s anomalies but detects a post-warm-up spike',
    (algorithm) => {
      const result = analyzePoints(buildBoundaryScenario(), { ...baseOptions, algorithm });

      expect(result.slice(0, baseOptions.baselineWindow).every((point) => !point.isAnomaly)).toBe(true);
      expect(result.slice(0, baseOptions.baselineWindow).every((point) => point.expected === null)).toBe(true);
      expect(result[baseOptions.baselineWindow].isAnomaly).toBe(true);
      expect(result[baseOptions.baselineWindow].score).toBeGreaterThanOrEqual(baseOptions.sensitivity);
    }
  );

  it('drops non-finite input points before they can poison later scores', () => {
    const points = [1, 2, 3, 4, 5].map((value, index) => buildRawPoint(index + 1, value));
    points.splice(2, 0, buildRawPoint(2.5, Number.NaN));
    points.push(buildRawPoint(Number.POSITIVE_INFINITY, 6));

    const result = analyzePoints(points, { ...baseOptions, algorithm: 'mad', baselineWindow: 3 });

    expect(result.map((point) => point.time)).toEqual([1, 2, 3, 4, 5]);
    expect(result.every((point) => Number.isFinite(point.score))).toBe(true);
    expect(result.every((point) => point.expected === null || Number.isFinite(point.expected))).toBe(true);
  });

  it('caps operational raw scores without changing a zero-baseline anomaly decision', () => {
    const points = [...Array.from({ length: 12 }, (_, index) => buildRawPoint(index, 0)), buildRawPoint(12, 100)];

    const result = analyzePoints(points, { ...baseOptions, algorithm: 'mad' });
    const spike = result[result.length - 1];

    expect(spike.isAnomaly).toBe(true);
    expect(spike.severityScore).toBe(100);
    expect(spike.score).toBe(MAX_RAW_SCORE);
    expect(spike.pointScore).toBe(MAX_RAW_SCORE);
  });

  it('classifies flat and irregularly sampled histories without treating regular cadence as gappy', () => {
    const flat = Array.from({ length: 8 }, (_, index) => buildRawPoint(index * 60_000, 0));
    const irregularTimes = [0, 60, 120, 240, 300, 420, 480, 600];
    const irregular = irregularTimes.map((seconds, index) => buildRawPoint(seconds * 1000, 100 + index));
    const regular = Array.from({ length: 8 }, (_, index) => buildRawPoint(index * 60_000, 100 + index));

    expect(analyzePoints(flat, { ...baseOptions, baselineWindow: 6 }).at(-1)?.dataQualityLabel).toBe('flatline');
    expect(analyzePoints(irregular, { ...baseOptions, baselineWindow: 6 }).at(-1)?.dataQualityLabel).toBe('gappy');
    expect(analyzePoints(regular, { ...baseOptions, baselineWindow: 6 }).at(-1)?.dataQualityLabel).toBe('healthy');
  });

  it('keeps a non-negative chart domain for non-negative metrics while preserving signed metrics', () => {
    expect(resolveValueDomain([-25, 10, 20], [10, 20]).min).toBe(0);
    expect(resolveValueDomain([-25, 10, 20], [-5, 20]).min).toBeLessThan(0);
  });

  it('applies Elastic-style high mean and low mean direction policies', () => {
    const highScenario = [...Array.from({ length: 12 }, (_, index) => buildRawPoint(index, 100)), buildRawPoint(12, 160)];
    const lowScenario = [...Array.from({ length: 12 }, (_, index) => buildRawPoint(index, 100)), buildRawPoint(12, 40)];

    const highAllowed = analyzePoints(highScenario, { ...baseOptions, anomalyDirection: 'high_mean' }).at(-1)!;
    const highBlocked = analyzePoints(highScenario, { ...baseOptions, anomalyDirection: 'low_mean' }).at(-1)!;
    const lowAllowed = analyzePoints(lowScenario, { ...baseOptions, anomalyDirection: 'low_mean' }).at(-1)!;
    const lowBlocked = analyzePoints(lowScenario, { ...baseOptions, anomalyDirection: 'high_mean' }).at(-1)!;

    expect(highAllowed.isAnomaly).toBe(true);
    expect(lowAllowed.isAnomaly).toBe(true);
    expect(highBlocked.isAnomaly).toBe(false);
    expect(lowBlocked.isAnomaly).toBe(false);
    expect(highBlocked.severityScore).toBe(0);
    expect(lowBlocked.severityLabel).toBe('normal');
  });

  it.each(['both', 'upper', '', 'HIGH_MEAN'])('does not silently mute an upward anomaly for direction %j', (direction) => {
    const points = [...Array.from({ length: 12 }, (_, index) => buildRawPoint(index, 100)), buildRawPoint(12, 160)];
    const result = analyzePoints(points, { ...baseOptions, anomalyDirection: direction as any });
    expect(result.at(-1)?.isAnomaly).toBe(true);
  });

  it('requires the configured N-of-M persistence and deviation floors', () => {
    const points = [
      ...Array.from({ length: 12 }, (_, index) => buildRawPoint(index, 100)),
      ...Array.from({ length: 4 }, (_, index) => buildRawPoint(12 + index, 160)),
    ];
    const result = analyzePoints(points, {
      ...baseOptions,
      algorithm: 'mad',
      anomalyDirection: 'high_mean',
      persistenceBuckets: 3,
      persistenceWindow: 4,
    });
    expect(result.slice(12, 14).every((point) => !point.isAnomaly)).toBe(true);
    expect(result[14].isAnomaly).toBe(true);

    const floorBlocked = analyzePoints(
      [...Array.from({ length: 12 }, (_, index) => buildRawPoint(index, 100)), buildRawPoint(12, 109)],
      { ...baseOptions, algorithm: 'mad', minimumAbsoluteDeviation: 10 }
    ).at(-1)!;
    expect(floorBlocked.isAnomaly).toBe(false);
    expect(floorBlocked.score).toBeGreaterThanOrEqual(baseOptions.sensitivity);
    expect(floorBlocked.severityScore).toBe(0);
  });

  it('holds, recovers, and cools down an incident without changing raw diagnostic scores', () => {
    const values = [...Array.from({ length: 6 }, () => [99, 101]).flat(), 108, 108, 108, 103, 100, 100, 108, 108, 108];
    const result = analyzePoints(
      values.map((value, index) => buildRawPoint(index, value)),
      {
        ...baseOptions,
        algorithm: 'mad',
        anomalyDirection: 'high_mean',
        persistenceBuckets: 2,
        persistenceWindow: 3,
        recoveryThreshold: 2,
        recoveryBuckets: 2,
        cooldownBuckets: 2,
      }
    );

    expect(result.some((point) => point.decisionState === 'open')).toBe(true);
    expect(result.some((point) => point.decisionState === 'recovering')).toBe(true);
    expect(result.some((point) => point.decisionState === 'cooldown')).toBe(true);
    expect(result.filter((point) => point.decisionState === 'cooldown').every((point) => point.severityScore === 0)).toBe(true);
  });
});
