# Release packages: 1.5.1

Current application/package version: **1.5.1**, API schema **3**. Earlier tags, notes and ZIPs remain unchanged as historical records. Use the matched 1.5.1 files below; do not mix versions or checksums.

## Artifacts

- `grafana-anomaly-detector-plugin-1.5.1.zip`: Grafana panel plugin.
- `grafana-anomaly-exporter-bundle-1.5.1.zip`: portable and RHEL exporter bundle.
- [Release notes](GITHUB_RELEASE_NOTES_v1.5.1.md)
- [New E2E guide](GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_v1.5.1_TR.md)
- [Illustrated PDF](../docs/e2e-guide-v1.5.1-tr.pdf)
- [Package inventory](PACKAGE_CONTENTS_v1.5.1_TR.md)
- `SHA256SUMS_v1.5.1.txt`: release integrity checksums.
- [Release gate and field limits](STATUS_v1.5.1.md)

Each ZIP contains `BUILD_INFO.json` with the source commit and per-file hashes. Maintainers must commit reviewed inputs, build the production plugin, run `python scripts/build_release.py --revision 1.5.1`, then `python scripts/check_release_packages.py --revision 1.5.1 --python /path/to/python3.9`. Commit generated assets separately; the release tag includes artifacts while the manifest identifies their source commit. Never include runtime state or secrets.

## Compatibility

- Grafana: `11.6.7` or later.
- Latest 1.5.1 UI gate: Grafana `12.4.0`; earlier release testing also covered `11.6.7`.
- Exporter Python: `3.9` or later.

## Exporter first start

The exporter zip now contains a ready-to-run `exporter/config.yml` plus two editable templates:

- `exporter/examples/config.prometheus.yml`
- `exporter/examples/config.influxdb.yml`

Prometheus source:

```bash
unzip grafana-anomaly-exporter-bundle-1.5.1.zip
cd grafana-anomaly-exporter-bundle
cp exporter/examples/config.prometheus.yml exporter/config.yml
vi exporter/config.yml
python3.9 -m venv .venv
.venv/bin/python -m pip install -r exporter/requirements.txt
export ANOMALY_PYTHON_BIN="$PWD/.venv/bin/python"
./portable-exporter.sh validate
./portable-exporter.sh start http://127.0.0.1:8090
```

InfluxDB 2.x source and sink:

```bash
cp exporter/examples/config.influxdb.yml exporter/config.yml
vi exporter/config.yml
export ANOMALY_SOURCE_INFLUX_ORG='my-org'
export ANOMALY_SOURCE_INFLUX_TOKEN='source-token'
export ANOMALY_SINK_INFLUX_TOKEN='sink-token'
./portable-exporter.sh validate
./portable-exporter.sh start
```

The Influx example intentionally uses separate source and score buckets to prevent score-feedback loops. The packaged `dynamic_rules.json` is empty; no development dashboard state is distributed.

The exporter API uses schema `3`. It supports lifecycle-aware decisions, explicit panel unregister, runtime-scope expiry, bounded requests, and separate `/health/live`, `/health/ready`, and `/health/dependencies` probes. Prometheus is optional when a non-Prometheus source and sink are selected.

## Validation

```bash
sha256sum -c SHA256SUMS_v1.5.1.txt
curl -fsS http://127.0.0.1:9110/health
curl -fsS http://127.0.0.1:9110/health/ready
curl -fsS http://127.0.0.1:9110/health/dependencies
curl -fsS http://127.0.0.1:9110/metrics | grep grafana_anomaly_build_info
```
