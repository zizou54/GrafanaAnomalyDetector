"""Run the complete browser gate with temporary, non-overwriting lab fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import base64
import time
import http.client

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:3000'


def main():
    if sys.argv[1:] != ['--local-lab']:
        raise SystemExit('Use --local-lab; this creates temporary localhost fixtures.')
    user, password = os.environ['QA_GRAFANA_USER'], os.environ['QA_GRAFANA_PASSWORD']
    token = base64.b64encode(f'{user}:{password}'.encode()).decode()

    def request(method, path, body=None):
        req = urllib.request.Request(BASE + path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Basic ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if method == 'GET' and exc.code == 404:
                return None
            raise

    ds_path = '/api/datasources/uid/anomaly-demo-testdata'
    dashboard_path = '/api/dashboards/uid/anomaly-detector-demo'
    deadline = time.monotonic() + 60
    while True:
        try:
            health = request('GET', '/api/health')
            if health and health.get('database') == 'ok':
                break
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise
        except (urllib.error.URLError, http.client.RemoteDisconnected):
            pass
        if time.monotonic() >= deadline:
            raise SystemExit('Grafana did not become healthy within 60 seconds.')
        time.sleep(2)
    # Existing objects could be user-owned: do not overwrite or delete them.
    if request('GET', ds_path) or request('GET', dashboard_path):
        raise SystemExit('Fixture UID already exists; inspect ownership before running this gate.')
    created_ds = created_dashboard = False
    try:
        request('POST', '/api/datasources', {'uid': 'anomaly-demo-testdata',
            'name': 'QA TestData', 'type': 'grafana-testdata-datasource',
            'access': 'proxy', 'isDefault': False})
        created_ds = True
        fixture = json.loads((ROOT / 'grafana-anomaly-detector-panel/provisioning/dashboards/dashboard.json').read_text())
        for panel in fixture['panels']:
            panel.setdefault('options', {})['scoreFeedMode'] = 'off'
        request('POST', '/api/dashboards/db', {'dashboard': fixture, 'overwrite': False})
        created_dashboard = True
        env = dict(os.environ, GRAFANA_URL=BASE, GRAFANA_ADMIN_USER=user,
                   GRAFANA_ADMIN_PASSWORD=password, PLAYWRIGHT_HTML_OPEN='never')
        executable = 'npx.cmd' if os.name == 'nt' else 'npx'
        result = subprocess.run([executable, 'playwright', 'test', '--workers=1',
                                 '--reporter=line'], cwd=ROOT / 'grafana-anomaly-detector-panel', env=env)
        return result.returncode
    finally:
        if created_dashboard:
            request('DELETE', dashboard_path)
        if created_ds:
            request('DELETE', ds_path)


if __name__ == '__main__':
    raise SystemExit(main())
