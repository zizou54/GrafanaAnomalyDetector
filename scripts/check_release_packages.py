"""Verify release archives without starting a server or writing runtime state."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--python', required=True, help='Interpreter used for extracted exporter smoke validation')
    args = parser.parse_args()
    release = ROOT / 'release'
    checksums = dict(line.split('  ', 1)[::-1] for line in
        (release / f'SHA256SUMS_v{args.revision}.txt').read_text().splitlines())
    commits = set()
    for filename, digest in checksums.items():
        file = release / filename
        assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, filename
        with zipfile.ZipFile(file) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
            assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in names)
            assert not any('/node_modules/' in name or '/__pycache__/' in name or name.endswith('.log') for name in names)
            manifest_name = next(name for name in names if name.endswith('/BUILD_INFO.json'))
            manifest = json.loads(archive.read(manifest_name))
            assert manifest['packageRevision'] == args.revision
            assert set(names) == set(manifest['files']) | {manifest_name}
            commits.add(manifest['sourceCommit'])
            for name, expected in manifest['files'].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
            if 'exporter-bundle' in filename:
                prefix = 'grafana-anomaly-exporter-bundle/'
                assert json.loads(archive.read(prefix + 'exporter/state/dynamic_rules.json')) == {'rules': []}
                for name in ['portable-exporter.sh', 'exporter/config.yml',
                             'exporter/examples/config.prometheus.yml', 'exporter/examples/config.influxdb.yml']:
                    content = archive.read(prefix + name)
                    assert content and b'\r\n' not in content
                assert (archive.getinfo(prefix + 'portable-exporter.sh').external_attr >> 16) & 0o111
                with tempfile.TemporaryDirectory() as directory:
                    archive.extractall(directory)
                    exporter = Path(directory) / prefix / 'exporter'
                    code = ('from app.config_loader import load_config; '
                            'from app import __version__; '
                            'assert __version__ == "' + manifest['applicationVersion'] + '"; '
                            '[load_config(p) for p in ["config.yml", "examples/config.prometheus.yml", "examples/config.influxdb.yml"]]; '
                            'print("Extracted exporter: imports and three configs PASS")')
                    subprocess.run([args.python, '-c', code], cwd=exporter, check=True)
            else:
                plugin = json.loads(archive.read('alpas-anomalydetector-panel/plugin.json'))
                assert plugin['info']['version'] == manifest['applicationVersion']
                assert 'alpas-anomalydetector-panel/module.js' in names
        print(filename + ': manifest, checksum and contents PASS')
    assert len(checksums) == 2 and len(commits) == 1
    print('Matched source commit: ' + next(iter(commits)))


if __name__ == '__main__':
    main()
