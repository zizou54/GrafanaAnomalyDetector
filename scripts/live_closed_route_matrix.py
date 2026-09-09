"""LOCAL LAB ONLY: register 36 isolated saved rules, verify readback, then remove them.

No browser feed is sent. Does not prove timestamp-aligned browser/backend parity.
"""
import json
import math
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, '/app')
from app.alert_queries import build_score_feed_registration
from app.config_loader import load_config
from app.dynamic_rules import DynamicRuleRegistry
from app.models import RuleConfig
from app.sources import build_source_reader


def api(path, payload=None, method=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request('http://127.0.0.1:9110/anomalyalarm' + path, data=data,
                      method=method, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main():
    if sys.argv[1:] != ['--local-lab']:
        raise SystemExit('Explicit --local-lab required; never run on production.')
    config = load_config(Path('/app/config.yml'))
    sources = [record for record in DynamicRuleRegistry('/app/state/dynamic_rules.json').list_records()
               if record.dashboard_uid == 'plugin-source-matrix' and record.scope_policy == 'saved'
               and record.scope_hash == 'saved' and 2 <= record.panel_id <= 7]
    assert len(sources) == 6, 'Expected six existing source demo rules'
    targets = ('prometheus', 'loki', 'influxdb', 'postgresql', 'clickhouse', 'elasticsearch')
    uid = 'qa-closed-' + uuid.uuid4().hex[:10]
    created = []
    results = []
    try:
        for source in sources:
            r = source.rule
            for target in targets:
                panel = len(created) + 1
                name = uid.replace('-', '_') + '_' + str(panel)
                created.append(panel)  # Also clean up an ambiguously completed POST.
                reply = api('/api/sync/panel', {
                    'schemaVersion': 3, 'dashboardUid': uid, 'panelId': panel,
                    'dashboardTitle': 'Isolated closed-panel QA', 'panelTitle': name,
                    'ruleNamePrefix': name, 'target': target, 'scopePolicy': 'saved',
                    'targets': [{'expr': r.query, 'refId': 'A', 'datasourceType': r.source_type,
                                 'datasourceUrl': r.datasource_url}],
                    'resolvedOptions': {'algorithm': r.algorithm, 'sensitivity': r.threshold,
                        'baselineWindow': r.baseline_window, 'seasonalitySamples': r.seasonality_samples,
                        'seasonalRefinement': r.seasonal_refinement, 'severityPreset': r.severity_preset,
                        'rangeSeconds': r.range_seconds, 'stepSeconds': r.step_seconds,
                        'bucketSpanSeconds': r.bucket_span_seconds}})
                assert reply.get('registered'), reply
                results.append(dict(source=r.source_type, target=target, rule=name))
        print(json.dumps(dict(registered=len(created), browser_feed_posts=0)), flush=True)
        time.sleep(150)
        now = time.time()
        with urlopen('http://127.0.0.1:9110/metrics', timeout=30) as response:
            metrics = response.read().decode().splitlines()
        for row in results:
            try:
                values = {}
                for line in metrics:
                    if not line.startswith('#') and re.search(r'\brule="' + re.escape(row['rule']) + '"', line):
                        values[line.split('{', 1)[0]] = float(line.rsplit(' ', 1)[1])
                state = values.get('grafana_anomaly_rule_data_state', 4)
                series_count = values.get('grafana_anomaly_rule_series_count', 0)
                age = now - values.get('grafana_anomaly_rule_last_data_timestamp_seconds', 0)
                query = build_score_feed_registration(row['rule'], row['target'], config)['query']
                if row['target'] == 'elasticsearch':
                    recipe = json.loads(query)
                    query = json.dumps({'query': recipe['query'], 'timeField': recipe['timeField'],
                        'metrics': [{'type': 'max', 'field': 'normalized_score'}],
                        'bucketAggs': [{'type': 'date_histogram', 'field': '@timestamp',
                                       'settings': {'interval': '1m'}}]})
                read = RuleConfig(name='qa_readback', source_type=row['target'], query=query)
                matrix = build_source_reader(read, config.global_config).query_range(now-120, now, 5)
                samples = [s for series in matrix for s in series.samples if math.isfinite(s.value)]
                row.update(samples=len(samples), passed=bool(samples) and state == 0 and series_count > 0 and age <= 120,
                           data_state=state, series_count=series_count, source_age_seconds=round(age, 2),
                           latest=max((s.timestamp for s in samples), default=0))
            except Exception as error:
                row.update(passed=False, error=type(error).__name__)
            print(json.dumps(row), flush=True)
    finally:
        cleanup_errors = []
        for panel in created:
            try:
                api('/api/sync/panel?' + urlencode({'dashboardUid': uid, 'panelId': panel}), method='DELETE')
            except Exception as error:
                cleanup_errors.append(dict(panel=panel, error=type(error).__name__))
        remaining = [r for r in api('/api/sync/rules')['rules'] if uid.replace('-', '_') in json.dumps(r)]
        print(json.dumps(dict(cleanup_errors=cleanup_errors, remaining=len(remaining))), flush=True)
        if cleanup_errors or remaining:
            raise RuntimeError('QA rule cleanup incomplete; inspect the isolated dashboard UID ' + uid)
    passed = len(results) == 36 and all(row.get('passed') for row in results)
    print(json.dumps(dict(passed=passed, routes=len(results), scope='actual source to saved backend rule to target readback; no browser feed')), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
