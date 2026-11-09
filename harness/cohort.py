"""Run independent episodes serially, preserving per-episode logs and reports."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--seeds', nargs='+', type=int, default=list(range(1,6)))
p.add_argument('--seconds', type=int, default=400)
p.add_argument('--name', default='dev-arc-v2')
p.add_argument('--mode', default='navigate')
p.add_argument('--width', type=float, default=1.25)
p.add_argument('--parameters',type=Path)
p.add_argument('--randomize',action='store_true')
p.add_argument('--workers',type=int,default=1)
args = p.parse_args()
directory = ROOT/'evidence/cohorts'/args.name
directory.mkdir(parents=True, exist_ok=True)
def episode(seed):
    target = directory/f'{args.mode}-{seed}'
    target.mkdir(parents=True, exist_ok=True)
    with (target/'run.log').open('w') as log:
        command = [sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','maze','--seed',str(seed),
                   '--seconds',str(args.seconds),'--mode',args.mode,'--width',str(args.width),'--output',str(target)]
        if args.parameters:
            command.extend(['--parameters',str(args.parameters)])
        if args.randomize:
            command.append('--randomize')
        proc = subprocess.run(command,stdout=log,stderr=log)
    if proc.returncode:
        return dict(seed=seed,error=True,log=str(target/'run.log'))
    r = json.loads((target/'report.json').read_text())
    return dict(seed=seed,exited=r['exited'],wrong_exit=r['wrong_exit'],status=r['status'],reason=r['reason'],
                          seconds=round(r['seconds'],2),thrash=round(r['thrash_peak'],3),warnings=len(r['warnings']),
                          wall_seconds=round(r['wall_seconds'],1))

if not 1 <= args.workers <= 4:
    raise ValueError('Use 1 to 4 single-threaded isolated episode workers')
with ThreadPoolExecutor(max_workers=args.workers) as executor:
    for future in as_completed([executor.submit(episode,seed) for seed in args.seeds]):
        print(json.dumps(future.result()),flush=True)
