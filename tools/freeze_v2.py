"""Seal the selected v2 controller and topology-disjoint evaluation protocol."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'evaluation/frozen-v2.json'


def inventory():
    patterns=['policy/*.py','policy/models/*','container/*.py','container/Dockerfile','container/entrypoint.sh',
        'config/*.json','harness/*.py','scene/flat.xml','scene/robot/**/*','requirements.txt',
        'review/evaluation_v2_protocol.json','tools/freeze_v2.py','tools/audit_v2.py','run.sh','screen_maze.py',
        'tests/*.py','tests/fixtures/*','scene/maze-0-w1.250.xml','scene/maze-0-w1.250.json',
        'tools/audit_image.py','tools/check_native_episode.py','tools/score_container.py','tools/native_report.py',
        'tools/run_kit.py','tools/prepare_kit.py','tools/preflight.py','g1-runner.json',
        '.github/workflows/native-arm64.yml']
    paths={p for pattern in patterns for p in ROOT.glob(pattern) if p.is_file() and '__pycache__' not in p.parts}
    manifest=ROOT/'vendor/builder-kit/UPSTREAM_FILES.json'
    paths.add(manifest)
    for row in json.loads(manifest.read_text())['files']:
        p=ROOT/'vendor/builder-kit'/row['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Canonical kit modified: '+row['path'])
        paths.add(p)
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def check():
    frozen=json.loads(TARGET.read_text())
    if frozen['files']!=inventory():
        raise ValueError('V2 source/settings/assets changed after final freeze')
    return frozen


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if a.check:
        frozen=check()
    else:
        if TARGET.exists():
            raise SystemExit('Refusing to replace an opened evaluation freeze')
        for name in ('config/control.json','config/navigation.json'):
            if not (ROOT/name).exists():
                raise SystemExit('Select and review configuration before freezing: '+name)
        frozen=dict(schema_version=2,files=inventory(),protocol=json.loads((ROOT/'review/evaluation_v2_protocol.json').read_text()))
        TARGET.write_text(json.dumps(frozen,indent=2)+'\n')
    print('V2 freeze matches:',len(frozen['files']),'files')
