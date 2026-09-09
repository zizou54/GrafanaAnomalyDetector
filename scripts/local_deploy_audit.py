"""Read-only local deployment audit; never creates rules or sends notifications."""
import base64
import json
import os
import re
import time
from urllib.request import Request, urlopen


def get(base, path, auth=False):
    headers = {}
    if auth:
        credentials = os.environ['QA_GRAFANA_USER'] + ':' + os.environ['QA_GRAFANA_PASSWORD']
        headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
    with urlopen(Request(base + path, headers=headers), timeout=30) as response:
        body = response.read().decode()
        return json.loads(body) if 'application/json' in response.headers.get('Content-Type', '') else body


def main():
    grafana = 'http://127.0.0.1:3000'
    exporter = 'http://127.0.0.1:9110'
    results = []

    def check(name, passed, evidence):
        row = dict(check=name, passed=bool(passed), evidence=evidence)
        results.append(row)
        print(json.dumps(row), flush=True)

    health = get(grafana, '/api/health')
    check('grafana_health', health.get('database') == 'ok', health.get('version'))
    for source in ('prometheus', 'loki', 'influxdb', 'postgresql', 'clickhouse', 'elasticsearch'):
        health = get(grafana, '/api/datasources/uid/demo-' + source + '/health', True)
        check('datasource_' + source, health.get('status') == 'OK', health.get('message'))
    for prefix in ('', '/anomalyalarm'):
        capabilities = get(exporter, prefix + '/api/capabilities')
        check('json_api_' + (prefix or 'root'), capabilities.get('exporterVersion') == '1.5.1',
              dict(version=capabilities.get('exporterVersion'), basePath=capabilities.get('basePath')))
    health = get(exporter, '/anomalyalarm/health/dependencies')
    check('sink_health', health.get('dependenciesHealthy') and len(health.get('sinks', [])) == 5,
          [{key: sink[key] for key in ('name', 'up', 'errorsTotal')} for sink in health.get('sinks', [])])
    rules = get(grafana, '/api/v1/provisioning/alert-rules', True)
    demo = [rule for rule in rules if rule['uid'].startswith('ms-')]
    check('alert_watchdog_present', any(rule['uid'] == 'ms-sink-watchdog' for rule in demo),
          [rule['uid'] for rule in demo])
    check('alert_not_silently_healthy_on_error', bool(demo) and all(
        rule.get('noDataState') != 'OK' and rule.get('execErrState') != 'OK'
        and rule.get('for') not in ('0s', '', None) for rule in demo),
        [dict(uid=r['uid'], noData=r.get('noDataState'), error=r.get('execErrState'), pending=r.get('for')) for r in demo])

    def sample():
        metrics = get(exporter, '/metrics')
        stamps = {}
        saved_names = {'local_' + name for name in (
            'prometheus_source_prometheus_metrics', 'loki_source_loki_sink',
            'influxdb_source_influxdb_sink', 'postgresql_source_elasticsearch_sink',
            'clickhouse_source_clickhouse_sink', 'elasticsearch_source_postgresql_sink')}
        for line in metrics.splitlines():
            if line.startswith('grafana_anomaly_rule_last_data_timestamp_seconds{'):
                match = re.search(r'rule="(local_[^"]+)"', line)
                if match and match[1] in saved_names:
                    stamps[match[1]] = float(line.rsplit(' ', 1)[1])
        return stamps

    before = sample()
    time.sleep(130)  # Includes minute-bucket sources; no feed/register POST is made.
    after = sample()
    check('saved_routes_advance_without_test_client_feed', len(before) == 6 and set(before) == set(after)
          and all(after[key] > before[key] for key in before),
          {key: dict(before=value, after=after.get(key)) for key, value in before.items()})
    print(json.dumps(dict(passed=all(row['passed'] for row in results), checks=len(results),
                          scope='6 saved routes, not 36 pairs, not timestamp-aligned browser parity or delivery')), flush=True)
    return 0 if all(row['passed'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
