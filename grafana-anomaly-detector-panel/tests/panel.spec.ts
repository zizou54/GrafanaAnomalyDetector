import { test, expect, type Page } from '@playwright/test';
import { cleanupIncidentFixture, installIncidentFixture } from './incident_fixture';

test.describe.configure({ mode: 'serial' });
test.setTimeout(90000);
test.afterEach(async ({ page }) => cleanupIncidentFixture(page));

const dashboardPaths = {
  testData: '/d-solo/anomaly-detector-demo/provisioned-anomaly-detector-demo?orgId=1&panelId=1',
  prometheusSource: '/d/plugin-source-matrix/grafana-anomaly-plugin-source-matrix?orgId=1&from=now-30m&to=now&viewPanel=2',
  lokiSource: '/d/plugin-source-matrix/grafana-anomaly-plugin-source-matrix?orgId=1&from=now-30m&to=now&viewPanel=3',
};

async function gotoSoloPanel(page: Page, path: string, title: string) {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  await expect(page.getByText(title, { exact: true }).first()).toBeVisible({ timeout: 60000 });
}

async function gotoSoloPanelOrSkip(page: Page, path: string, title: string) {
  const uid = path.split('/')[2];
  const response = await page.request.get(`/api/dashboards/uid/${uid}`);
  test.skip(response.status() === 404, `Dashboard ${uid} is not provisioned in the current stack.`);
  expect(response.ok(), `Dashboard ${uid} must be readable`).toBe(true);
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: title, exact: true }).first()).toBeVisible({ timeout: 60000 });
}

async function selectFirstAnomaly(page: Page) {
  const firstSummaryRow = page.getByRole('button', { name: /Detected incident / }).first();
  await expect(firstSummaryRow).toBeVisible({ timeout: 60000 });
  await firstSummaryRow.click();
}

async function selectFirstAnomalyIfPresent(page: Page): Promise<boolean> {
  const firstSummaryRow = page.getByRole('button', { name: /Detected incident / }).first();
  const hasIncident = await firstSummaryRow
    .waitFor({ state: 'visible', timeout: 30000 })
    .then(() => true)
    .catch(() => false);

  if (!hasIncident) {
    await expect(page.getByText(/No operationally relevant incidents|No clustered incidents/).first()).toBeVisible({ timeout: 60000 });
    return false;
  }

  await firstSummaryRow.click();
  return true;
}

async function expectVisiblePageText(page: Page, fragment: string) {
  await expect
    .poll(async () => {
      return page.locator('body').evaluate((element) => (element as HTMLElement).innerText);
    }, { timeout: 60000 })
    .toContain(fragment);
}

test('renders the provisioned TestData panel and exposes point-level analysis details', async ({ page }, testInfo) => {
  // This fixture contains a single spike, not three repeated breaches. Keep the
  // product defaults unchanged and explicitly exercise point-level inspection.
  await page.route((url) => url.pathname === '/api/dashboards/uid/anomaly-detector-demo'
    || url.pathname.endsWith('/dashboards/anomaly-detector-demo/dto'), async (route) => {
    const response = await route.fetch();
    if (!response.ok()) {
      await route.fulfill({ response });
      return;
    }
    const payload = await response.json();
    for (const panel of (payload.dashboard ?? payload.spec).panels) {
      panel.options = { ...panel.options, scoreFeedMode: 'off', persistenceBuckets: 1,
        persistenceWindow: 1, recoveryBuckets: 1, cooldownBuckets: 0 };
    }
    await route.fulfill({ response, json: payload });
  });
  await gotoSoloPanelOrSkip(page, dashboardPaths.testData, 'Anomaly Detector');

  await expect(page.getByText('Detected incidents', { exact: true }).first()).toBeVisible({ timeout: 60000 });
  await expect(page.getByText('Anomaly inspector', { exact: true })).toBeVisible();
  await expect(page.getByText('Active detection profile', { exact: true })).toBeVisible();

  await selectFirstAnomaly(page);

  const inspector = page.getByRole('complementary', { name: 'Anomaly inspector', exact: true });
  for (const label of ['Value', 'Expected', 'Deviation', 'Confidence', 'Raw detection score']) {
    await expect(inspector.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(inspector.getByText('415', { exact: true })).toBeVisible();
  await expect(inspector.getByText('249.25', { exact: true })).toBeVisible();
  await expect(inspector.getByText('Healthy data', { exact: true })).toBeVisible();
  await expect(page.getByText('n/a%', { exact: true })).toHaveCount(0);
  await expect(inspector.getByRole('button', { name: 'Copy rule labels' })).toBeEnabled();
  await expect(page.getByRole('img', { name: 'Incident timeline overview', exact: true }).locator('text')).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath('testdata-inspector.png'), fullPage: true });
});

test('uses deterministic incidents to test Prometheus panel actions with live score-feed registration', async ({ page, context }) => {
  const fixtureFrames = await installIncidentFixture(page);
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://127.0.0.1:3000' });
  await gotoSoloPanel(page, dashboardPaths.prometheusSource, 'Prometheus source -> Prometheus metrics');

  await expect(page.getByText('Anomaly score feed', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sync score feed' })).toBeVisible();
  await expect(page.locator('[aria-label="Detected incident overview"]').first()).toBeVisible();

  await page.getByRole('button', { name: 'Sync score feed' }).click();
  await expect(page.getByText(/Published \d+ plugin-computed score series/)).toBeVisible({ timeout: 30000 });
  await expect(page.getByText('Prometheus healthy', { exact: true })).toBeVisible();
  await expect(page.locator('[aria-label="Score feed target health"]').getByText('Prometheus', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Show synced rules' })).toBeVisible();

  await page.getByRole('button', { name: 'Show synced rules' }).click();
  await expect(page.getByText('Alert rule query', { exact: true })).toBeVisible();
  await expect(page.getByText('PromQL', { exact: true }).first()).toBeVisible();
  await expectVisiblePageText(page, 'grafana_anomaly_rule_score{rule=');

  await selectFirstAnomaly(page);

  expect(fixtureFrames()).toBeGreaterThan(0);
  await expect(page.getByText('Why is this anomalous?', { exact: true })).toBeVisible();
  await expect(page.getByText('Deviation', { exact: true })).toBeVisible();
  await expect(page.getByText('Confidence', { exact: true }).first()).toBeVisible();
  const inspector = page.locator('[aria-label="Anomaly inspector"]').first();
  const popupPromise = page.waitForEvent('popup');
  await expect(inspector.getByRole('button', { name: 'Open alert rule builder' })).toBeEnabled();
  await expect(inspector.getByRole('button', { name: 'Copy rule labels' })).toBeEnabled();
  await inspector.getByRole('button', { name: 'Open alert rule builder' }).click();
  const alertBuilder = await popupPromise;
  await expect(alertBuilder).toHaveURL(/\/alerting\/new/);
  await expect(alertBuilder).toHaveURL(/label_alert_family=anomaly_detector/);
  await expect(alertBuilder).toHaveURL(/label_severity=major/);
  const alertBuilderUrl = new URL(alertBuilder.url());
  expect(alertBuilderUrl.searchParams.get('ruleName')).toContain('Prometheus source -> Prometheus metrics');
  expect(alertBuilderUrl.searchParams.get('query')).toContain('grafana_anomaly_rule_score');
  await alertBuilder.close();

  await inspector.getByRole('button', { name: 'Copy rule labels' }).click();
  await expect(page.getByText('Copied suggested alert labels.')).toBeVisible({ timeout: 30000 });

  await expect(inspector.getByRole('button', { name: 'Copy alert query' })).toBeEnabled();
  await inspector.getByRole('button', { name: 'Copy alert query' }).click();
  await expect(page.getByText('Copied the alert query for Grafana Alerting.')).toBeVisible({ timeout: 30000 });

  const createAnnotation = inspector.getByRole('button', { name: 'Create annotation' });
  await expect(createAnnotation).toBeEnabled();
  await createAnnotation.click();
  await expect(page.getByText('Created a Grafana annotation for the selected anomaly.')).toBeVisible({ timeout: 30000 });
});

test('renders the source-matrix Loki panel with target-specific alert query preview', async ({ page }) => {
  await gotoSoloPanel(page, dashboardPaths.lokiSource, 'Loki source -> Loki sink');

  await expect(page.getByText('Detected incidents', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Alerting & automation', { exact: true })).not.toBeVisible();
  await expect(page.getByText('Alert rule export', { exact: true })).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Sync score feed' })).toBeVisible();

  await page.getByRole('button', { name: 'Sync score feed' }).click();
  await expect(page.getByText(/Published \d+ plugin-computed score series/)).toBeVisible({ timeout: 30000 });

  const hasIncident = await selectFirstAnomalyIfPresent(page);
  if (hasIncident) {
    await expect(page.getByText('Why is this anomalous?', { exact: true })).toBeVisible();
    await expect(page.getByText('Query preview', { exact: true })).toBeVisible();
  } else {
    await page.getByRole('button', { name: 'Show synced rules' }).click();
    await expect(page.getByText('Alert rule query', { exact: true })).toBeVisible();
    await expect(page.getByText('LogQL', { exact: true }).first()).toBeVisible();
  }
  await expectVisiblePageText(page, 'record_type="rule"');
});







