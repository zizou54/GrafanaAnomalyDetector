import { test, expect } from '@grafana/plugin-e2e';
import { cleanupIncidentFixture, installIncidentFixture } from './incident_fixture';

test('renders opt-in Harmonic without saving the dashboard or registering a feed', async ({ page }, testInfo) => {
  test.setTimeout(90000);
  await installIncidentFixture(page);
  await page.route((url) => url.pathname === '/api/dashboards/uid/plugin-source-matrix' || url.pathname.endsWith('/dashboards/plugin-source-matrix/dto'), async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const panel = (body.dashboard ?? body.spec).panels.find((entry: { id: number }) => entry.id === 2);
    expect(panel).toBeTruthy();
    panel.options = { ...panel.options, setupMode: 'advanced', algorithm: 'harmonic', seasonalitySamples: 24, scoreFeedMode: 'off' };
    await route.fulfill({ response, json: body });
  });
  try {
    await page.goto('/d/plugin-source-matrix/grafana-anomaly-plugin-source-matrix?orgId=1&from=now-30m&to=now&viewPanel=2');
    await expect(page.getByText('Prometheus source -> Prometheus metrics', { exact: true }).first()).toBeVisible({ timeout: 60000 });
    await expect(page.getByText('Algorithm: harmonic', { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/two full cycles|48 samples of warm-up/).first()).toBeVisible();
    await expect(page.getByText('Active detection profile', { exact: true }).first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('harmonic-panel.png'), fullPage: true });
  } finally {
    await cleanupIncidentFixture(page);
  }
});
