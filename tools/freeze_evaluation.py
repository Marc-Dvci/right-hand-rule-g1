"""Freeze code, assets and settings before opening the final evaluation seeds."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT/'evaluation/frozen.json'


def inventory():
    patterns = ['policy/*.py','policy/models/*','container/timing.py','config/*.json',
                'harness/evaluate.py','harness/cohort.py','harness/kit.py','harness/scenes.py',
                'harness/scoring.py','harness/randomization.py','scene/robot/**/*',
                'evaluation_protocol.json','requirements.txt']
    paths = sorted({p for pattern in patterns for p in ROOT.glob(pattern) if p.is_file()})
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def check():
    frozen = json.loads(TARGET.read_text())
    if frozen['files'] != inventory():
        raise ValueError('Frozen evaluation code/configuration changed; the old evaluation does not qualify this version.')
    return frozen


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check',action='store_true')
    a = p.parse_args()
    if a.check:
        result = check()
    else:
        if TARGET.exists():
            raise SystemExit('Refusing to replace an existing final freeze.')
        result = dict(schema_version=1,files=inventory(),protocol=json.loads((ROOT/'evaluation_protocol.json').read_text()))
        TARGET.parent.mkdir(exist_ok=True)
        TARGET.write_text(json.dumps(result,indent=2)+'\n')
    print('Frozen evaluation:',len(result['files']),'files; protocol seeds:',len(result['protocol']['final_seeds']))
