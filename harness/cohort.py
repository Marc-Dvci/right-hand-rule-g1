"""Run independent episodes serially, preserving per-episode logs and reports."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--seeds', nargs='+', type=int, default=list(range(1,6)))
p.add_argument('--seconds', type=int, default=400)
p.add_argument('--name', default='dev-arc-v2')
p.add_argument('--mode', default='navigate')
args = p.parse_args()
directory = ROOT/'evidence/cohorts'/args.name
directory.mkdir(parents=True, exist_ok=True)
for seed in args.seeds:
    target = directory/f'{args.mode}-{seed}'
    target.mkdir(parents=True, exist_ok=True)
    with (target/'run.log').open('w') as log:
        proc = subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','maze','--seed',str(seed),
                               '--seconds',str(args.seconds),'--mode',args.mode,'--output',str(target)],stdout=log,stderr=log)
    if proc.returncode:
        print('ERROR', seed, 'log', target/'run.log', flush=True)
        continue
    r = json.loads((target/'report.json').read_text())
    print(json.dumps(dict(seed=seed,exited=r['exited'],wrong_exit=r['wrong_exit'],status=r['status'],reason=r['reason'],
                          seconds=round(r['seconds'],2),thrash=round(r['thrash_peak'],3),warnings=len(r['warnings']),
                          wall_seconds=round(r['wall_seconds'],1))), flush=True)
