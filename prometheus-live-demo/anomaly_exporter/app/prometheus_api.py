from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

from .http_security import open_same_origin
from .models import PrometheusRangeSeries, PrometheusSample


class PrometheusQueryError(RuntimeError):
    pass


def _parse_sample(pair: object, labels: dict[str, str]) -> PrometheusSample | None:
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return None
    try:
        timestamp, value = float(pair[0]), float(pair[1])
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(timestamp) or not math.isfinite(value):
        return None
    return PrometheusSample(labels=labels, value=value, timestamp=timestamp)


class PrometheusClient:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds

    def instant_query(self, query: str, evaluation_time: float) -> list[PrometheusSample]:
        params = urllib.parse.urlencode({'query': query, 'time': f'{evaluation_time:.3f}'})
        url = f'{self.base_url}/api/v1/query?{params}'
        request = urllib.request.Request(url=url, method='GET')

        try:
            with open_same_origin(request, self.timeout_seconds) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except Exception as exc:  # noqa: BLE001
            raise PrometheusQueryError(f'Query to Prometheus failed for {query!r}: {exc}') from exc

        if payload.get('status') != 'success':
            raise PrometheusQueryError(f'Prometheus returned non-success status for {query!r}: {payload}')

        data = payload.get('data', {})
        result_type = data.get('resultType')
        result = data.get('result', [])

        if result_type == 'vector':
            samples: list[PrometheusSample] = []
            for row in result:
                metric = {str(key): str(value) for key, value in row.get('metric', {}).items()}
                sample = _parse_sample(row.get('value'), metric)
                if sample is not None:
                    samples.append(sample)
            return samples

        if result_type == 'scalar':
            sample = _parse_sample(result, {})
            return [sample] if sample is not None else []

        raise PrometheusQueryError(f'Unsupported Prometheus result type {result_type!r} for query {query!r}.')

    def range_query(self, query: str, start_time: float, end_time: float, step_seconds: int) -> list[PrometheusRangeSeries]:
        params = urllib.parse.urlencode(
            {
                'query': query,
                'start': f'{start_time:.3f}',
                'end': f'{end_time:.3f}',
                'step': max(1, int(step_seconds)),
            }
        )
        url = f'{self.base_url}/api/v1/query_range?{params}'
        request = urllib.request.Request(url=url, method='GET')

        try:
            with open_same_origin(request, self.timeout_seconds) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except Exception as exc:  # noqa: BLE001
            raise PrometheusQueryError(f'Range query to Prometheus failed for {query!r}: {exc}') from exc

        if payload.get('status') != 'success':
            raise PrometheusQueryError(f'Prometheus returned non-success status for range query {query!r}: {payload}')

        data = payload.get('data', {})
        result_type = data.get('resultType')
        result = data.get('result', [])
        if result_type != 'matrix':
            raise PrometheusQueryError(f'Unsupported Prometheus range result type {result_type!r} for query {query!r}.')

        series: list[PrometheusRangeSeries] = []
        for row in result:
            metric = {str(key): str(value) for key, value in row.get('metric', {}).items()}
            samples: list[PrometheusSample] = []
            for pair in row.get('values', []):
                sample = _parse_sample(pair, metric)
                if sample is not None:
                    samples.append(sample)
            if samples:
                series.append(PrometheusRangeSeries(labels=metric, samples=samples))
        return series
