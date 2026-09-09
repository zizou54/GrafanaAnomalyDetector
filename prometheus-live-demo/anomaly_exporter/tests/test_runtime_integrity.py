from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.algorithms import evaluate_series
from app.models import AppConfig, GlobalConfig, RuleConfig, SeriesState
from app.server import ExporterRuntime
from app.sources import build_source_reader
from app.prometheus_api import PrometheusQueryError


class RuntimeIntegrityTests(unittest.TestCase):
    def test_workload_counts_range_and_instant_inputs_before_bucketing(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = ExporterRuntime(str(Path(directory) / 'config.yml'))
            range_rule = RuleConfig(name='range', query='fixture', range_seconds=60,
                                    bucket_span_seconds=30, target_sinks=[])
            instant_rule = RuleConfig(name='instant', query='fixture', target_sinks=[])
            runtime.current_config = AppConfig(GlobalConfig(), [range_rule, instant_rule])
            samples = [SimpleNamespace(timestamp=float(i * 10), value=100., labels={}) for i in range(6)]
            matrix = [SimpleNamespace(labels={}, samples=samples)]
            with patch.object(runtime, 'maybe_reload_config'), \
                 patch('app.server.build_source_reader') as reader, \
                 patch('app.server.PrometheusClient.instant_query', return_value=samples[-1:]):
                reader.return_value.query_range.return_value = matrix
                runtime.run_once()
            self.assertEqual(runtime.last_input_points, 7)
            self.assertEqual(runtime.last_input_series, 2)
            self.assertEqual(runtime.query_success, {'range': 1, 'instant': 1})
            runtime.sink_manager.close()

    def test_evaluation_uses_monotonic_clock_and_exposes_phase_timings(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = ExporterRuntime(str(Path(directory) / 'config.yml'))
            runtime.current_config = AppConfig(GlobalConfig(), [])
            # Wall clock can move backwards without making durations negative.
            with patch.object(runtime, 'maybe_reload_config'), \
                 patch('app.server.time.time', return_value=-100.), \
                 patch('app.server.time.monotonic', side_effect=[10., 11., 14., 15., 20., 22.]):
                runtime.run_once()
            self.assertEqual(runtime.last_evaluation_timestamp, -100.)
            self.assertEqual(runtime.last_evaluation_duration_seconds, 12.)
            self.assertEqual(runtime.last_source_duration_seconds, 3.)
            self.assertEqual(runtime.last_scoring_duration_seconds, 5.)
            payload = runtime.metrics_payload.decode()
            self.assertIn('grafana_anomaly_source_query_duration_seconds 3.000000', payload)
            self.assertIn('grafana_anomaly_scoring_duration_seconds 5.000000', payload)
            self.assertIn('grafana_anomaly_evaluation_input_points 0', payload)
            runtime.sink_manager.close()

    def test_failed_source_resets_completed_workload_without_hiding_error(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = ExporterRuntime(str(Path(directory) / 'config.yml'))
            rule = RuleConfig(name='failed', query='fixture', target_sinks=[])
            runtime.current_config = AppConfig(GlobalConfig(), [rule])
            runtime.last_input_points = 123
            runtime.last_input_series = 3
            with patch.object(runtime, 'maybe_reload_config'), \
                 patch('app.server.PrometheusClient.instant_query', side_effect=PrometheusQueryError('offline')):
                runtime.run_once()
            self.assertEqual(runtime.last_input_points, 0)
            self.assertEqual(runtime.last_input_series, 0)
            self.assertEqual(runtime.query_success, {'failed': 0})
            self.assertIn('offline', runtime.last_error)
            self.assertGreaterEqual(runtime.last_source_duration_seconds, 0.)
            runtime.sink_manager.close()

    def test_source_resolution_does_not_mutate_reload_comparison_input(self):
        rule = RuleConfig(name='immutable', query='fixture')
        with patch.dict('os.environ', {'ANOMALY_SOURCE_PROMETHEUS_URL': 'http://source.invalid'}):
            reader = build_source_reader(rule, GlobalConfig())
        self.assertEqual(rule.datasource_url, '')
        self.assertEqual(reader.rule.datasource_url, 'http://source.invalid')

    def test_open_panel_preview_cannot_mask_backend_failure_or_duplicate_series(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = ExporterRuntime(str(Path(directory) / 'config.yml'))
            rule = RuleConfig(name='persistent', query='fixture')
            state = SeriesState.create(rule.history_limit, rule.baseline_window)
            series = evaluate_series(state, rule, 'fixture', {}, 100, time.time())
            backend_rule = runtime._build_rule_snapshot(rule, [], time.time(), 'source unavailable')
            preview = replace(series, normalized_score=100, is_anomaly=True)
            preview_rule = replace(backend_rule, data_state='ok', max_score=100)
            runtime.rule_snapshots = [backend_rule]
            runtime.pushed_feeds = {'panel': ([preview], [preview_rule], time.time())}
            self.assertEqual(runtime._merged_series_snapshots_locked(), [])
            self.assertEqual(runtime._merged_rule_snapshots_locked(), [backend_rule])
            self.assertEqual(runtime._merged_query_success_locked({'persistent': 0}), {'persistent': 0})
            runtime.series_snapshots = [series]
            self.assertEqual(runtime._merged_series_snapshots_locked(), [series])
            runtime.sink_manager.close()

    def test_expired_preview_does_not_report_query_success(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = ExporterRuntime(str(Path(directory) / 'config.yml'))
            snapshot = runtime._build_rule_snapshot(RuleConfig(name='preview', query='fixture'), [], 0)
            runtime.pushed_feeds = {'expired': ([], [snapshot], time.time() - 3600)}
            self.assertEqual(runtime._merged_query_success_locked({}), {})
            runtime.sink_manager.close()

    def test_panel_timestamp_cannot_refresh_backend_evaluation_heartbeat(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yml'
            path.write_text('rules: []\n', encoding='utf-8')
            runtime = ExporterRuntime(str(path))
            runtime.last_evaluation_timestamp = 100.0
            payload = {'dashboardUid': 'fixture', 'panelId': 1, 'ruleName': 'preview',
                       'target': 'prometheus', 'rule': {'timestamp': 9999999999},
                       'series': [{'label': 'fixture', 'value': 100, 'timestamp': 9999999999}]}
            with patch.object(runtime, '_render_metrics', return_value=b'') as render:
                runtime.ingest_score_feed(payload)
            self.assertEqual(render.call_args.kwargs['evaluation_time'], 100.0)
            runtime.sink_manager.close()

    def test_reload_preserves_only_unchanged_rule_and_source_history(self):
        for change in ('unchanged', 'query', 'algorithm', 'threshold', 'source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.yml'
                path.write_text('{}', encoding='utf-8')
                runtime = ExporterRuntime(str(path))
                original = RuleConfig(name='same_name', query='old_metric', algorithm='mad')
                original_global = GlobalConfig(prometheus_url='http://old-source.invalid')
                runtime.current_config = AppConfig(original_global, [original])
                state = SeriesState.create(original.history_limit, original.baseline_window)
                evaluate_series(state, original, 'old_metric', {}, 100, 100.0)
                runtime.rule_states = {original.name: {'series': state}}
                runtime.query_success = {original.name: 1}
                changes = {'query': {'query': 'new_metric'}, 'algorithm': {'algorithm': 'ewma'},
                           'threshold': {'threshold': 8}}
                updated = replace(original, **changes.get(change, {}))
                global_config = replace(original_global, prometheus_url='http://new-source.invalid') if change == 'source' else original_global
                with patch.object(runtime, '_load_combined_config', return_value=AppConfig(global_config, [updated])):
                    runtime.maybe_reload_config(force=True)
                if change == 'unchanged':
                    self.assertIs(runtime.rule_states[original.name]['series'], state)
                    self.assertEqual(runtime.query_success[original.name], 1)
                else:
                    self.assertEqual(runtime.rule_states[original.name], {}, 'old observations must not score a different rule')
                    self.assertEqual(runtime.query_success[original.name], 0)
                runtime.sink_manager.close()


if __name__ == '__main__':
    unittest.main()
