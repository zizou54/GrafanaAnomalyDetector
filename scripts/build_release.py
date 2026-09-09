"""Build versioned release ZIPs from an already tested production plugin build.

No runtime registry, credentials, caches, or local QA evidence is packaged.
Run after committing source and building the plugin. Output is deterministic
for the same source commit and dist bytes.
"""
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive(path, files, metadata):
    manifest = dict(metadata, files={name: sha(data) for name, data in sorted(files.items())})
    prefix = next(iter(files)).split('/')[0]
    files = dict(files)
    files[prefix + '/BUILD_INFO.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for name, digest in manifest['files'].items():
            assert sha(z.read(name)) == digest, name
    print(f'{path.name}: {len(files)} files; sha256={sha(path.read_bytes())}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-r\d+)?', args.revision):
        parser.error('Invalid package revision')
    panel = ROOT / 'grafana-anomaly-detector-panel'
    exporter = ROOT / 'prometheus-live-demo/anomaly_exporter'
    version = json.loads((panel / 'package.json').read_text())['version']
    plugin = json.loads((panel / 'dist/plugin.json').read_text())
    assert plugin['info']['version'] == version == args.revision.split('-r')[0]
    assert f"__version__ = '{version}'" in (exporter / 'app/__init__.py').read_text()
    document_names = [f'PACKAGE_CONTENTS_v{version}_TR.md',
                      f'GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_v{version}_TR.md']
    release = ROOT / 'release'
    for name in document_names:
        if not (release / name).is_file():
            parser.error(f'Missing version-matched release document: {name}')
    source_paths = ['grafana-anomaly-detector-panel', 'prometheus-live-demo/anomaly_exporter',
                    'scripts/build_release.py', 'docs/ANOMALYALARM_PROXY_TR.md',
                    *['release/' + name for name in document_names]]
    if version == '1.5.1':
        source_paths += ['release/screenshots/v1.5.1', 'release/STATUS_v1.5.1.md',
                         'docs/HARMONIC_151_USAGE_TR.md', 'docs/e2e-guide-v1.5.1-tr.pdf']
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all',
                                     '--', *source_paths], cwd=ROOT, text=True)
    if dirty.strip():
        parser.error('Commit reviewed package inputs before building; sourceCommit must identify exact source.')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    metadata = {'packageRevision': args.revision, 'applicationVersion': version, 'sourceCommit': commit}

    def normalized(path):
        data = path.read_bytes()
        if path.suffix in {'.py', '.sh', '.yml', '.md', '.txt', '.service', '.example', '.snippet'}:
            data = data.replace(b'\r\n', b'\n')
        return data

    plugin_files = {plugin['id'] + '/' + p.relative_to(panel / 'dist').as_posix(): p.read_bytes()
                    for p in sorted((panel / 'dist').rglob('*')) if p.is_file()}
    assert any(name.endswith('/module.js') for name in plugin_files)
    archive(release / f'grafana-anomaly-detector-plugin-{args.revision}.zip', plugin_files, metadata)

    prefix = 'grafana-anomaly-exporter-bundle/'
    files = {}
    for directory, suffixes in [('app', {'.py'}), ('examples', {'.yml', '.md'})]:
        for p in sorted((exporter / directory).rglob('*')):
            if p.is_file() and p.suffix in suffixes:
                files[prefix + 'exporter/' + p.relative_to(exporter).as_posix()] = normalized(p)
    for name in ['config.yml', 'main.py', 'requirements.txt', 'requirements-postgresql.txt', 'rules.yml']:
        files[prefix + 'exporter/' + name] = normalized(exporter / name)
    files[prefix + 'portable-exporter.sh'] = normalized(exporter / 'portable-exporter.sh')
    for p in sorted((exporter / 'packaging').iterdir()):
        if p.is_file():
            files[prefix + p.name] = normalized(p)
    files[prefix + 'exporter/state/dynamic_rules.json'] = b'{"rules": []}\n'
    for source, destination in [
        (document_names[0], 'README_TR.md'),
        (document_names[1],
         'GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_TR.md')]:
        files[prefix + destination] = normalized(release / source)
    files[prefix + 'ANOMALYALARM_PROXY_TR.md'] = normalized(ROOT / 'docs/ANOMALYALARM_PROXY_TR.md')
    if version == '1.5.1':
        # Keep the offline guide self-contained while retaining repository links in GitHub Markdown.
        guide = normalized(release / document_names[1]).replace(b'(../docs/', b'(docs/')
        files[prefix + 'GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_TR.md'] = guide
        files[prefix + document_names[1]] = guide
        files[prefix + 'STATUS_v1.5.1.md'] = normalized(release / 'STATUS_v1.5.1.md')
        files[prefix + 'release/STATUS_v1.5.1.md'] = normalized(release / 'STATUS_v1.5.1.md')
        for name in ['ANOMALYALARM_PROXY_TR.md', 'HARMONIC_151_USAGE_TR.md', 'e2e-guide-v1.5.1-tr.pdf']:
            files[prefix + 'docs/' + name] = normalized(ROOT / 'docs' / name)
        for p in sorted((release / 'screenshots/v1.5.1').glob('*.png')):
            files[prefix + 'screenshots/v1.5.1/' + p.name] = p.read_bytes()
    archive(release / f'grafana-anomaly-exporter-bundle-{args.revision}.zip', files, metadata)
    packages = [release / f'grafana-anomaly-detector-plugin-{args.revision}.zip',
                release / f'grafana-anomaly-exporter-bundle-{args.revision}.zip']
    (release / f'SHA256SUMS_v{args.revision}.txt').write_text(
        ''.join(f'{sha(p.read_bytes())}  {p.name}\n' for p in packages), encoding='utf-8')


if __name__ == '__main__':
    main()
