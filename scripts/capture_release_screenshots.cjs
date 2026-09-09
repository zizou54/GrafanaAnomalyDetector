// Read-only local UI documentation capture; authenticate with the E2E auth state.
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '..');
const localRequire = createRequire(path.join(root, 'grafana-anomaly-detector-panel/package.json'));
const { chromium, expect } = localRequire('@playwright/test');

(async () => {
  if (process.argv[2] !== '--local-lab') throw new Error('Use --local-lab.');
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 1920, height: 1440 },
      colorScheme: 'light', storageState: path.join(root, 'grafana-anomaly-detector-panel/playwright/.auth/admin.json') });
    const page = await context.newPage();
    const destination = path.join(root, 'release/screenshots/v1.5.1');
    fs.mkdirSync(destination, { recursive: true });
    for (const [id, name] of [[2, 'prometheus-overview'], [4, 'influx-overview'], [5, 'postgres-elastic-overview']]) {
      await page.goto(`http://127.0.0.1:3000/d/plugin-source-matrix/grafana-anomaly-plugin-source-matrix?orgId=1&from=now-30m&to=now&viewPanel=${id}&theme=light`);
      await expect(page.getByRole('img', { name: 'Anomaly chart', exact: true })).toBeVisible({ timeout: 90000 });
      await expect(page.getByText('Active detection profile', { exact: true }).first()).toBeVisible();
      await page.screenshot({ path: path.join(destination, name + '.png'), fullPage: true });
      console.log('Captured ' + name);
    }
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
