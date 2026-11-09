"""Run isolated single-threaded episodes, preserving every log and report."""
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
p.add_argument('--control-config',type=Path)
p.add_argument('--randomize',action='store_true')
p.add_argument('--workers',type=int,default=1)
p.add_argument('--transport',action='store_true')
p.add_argument('--transport-config',type=Path)
p.add_argument('--latency-steps',type=int,choices=(0,1,2))
p.add_argument('--final',action='store_true',help='Use the frozen final protocol; never replace evidence')
args = p.parse_args()
directory = ROOT/'evidence/cohorts'/args.name
if args.final:
    sys.path.insert(0,str(ROOT))
    from tools.freeze_evaluation import check
    frozen = check()
    args.seeds = frozen['protocol']['final_seeds']
    if not (args.randomize and args.transport and args.latency_steps==0 and args.mode=='navigate' and args.seconds==400):
        raise ValueError('Final primary evaluation requires nominal timing, randomization, transport and 400 seconds')
    for value,name in ((args.parameters,'navigation'),(args.transport_config,'deployment')):
        if value is None or value.resolve() != (ROOT/f'config/{name}.json').resolve():
            raise ValueError('Final evaluation must use the frozen configuration files')
    if directory.exists():
        raise ValueError('Final evidence directory already exists; refusing to overwrite it')
directory.mkdir(parents=True, exist_ok=True)
if args.final:
    (directory/'freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')
def episode(seed):
    target = directory/f'{args.mode}-{seed}'
    target.mkdir(parents=True, exist_ok=True)
    with (target/'run.log').open('w') as log:
        command = [sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','maze','--seed',str(seed),
                   '--seconds',str(args.seconds),'--mode',args.mode,'--width',str(args.width),'--output',str(target)]
        if args.parameters:
            command.extend(['--parameters',str(args.parameters)])
        if args.control_config:
            command.extend(['--control-config',str(args.control_config)])
        if args.randomize:
            command.append('--randomize')
        if args.transport:
            command.append('--transport')
        if args.transport_config:
            command.extend(['--transport-config',str(args.transport_config)])
        if args.latency_steps is not None:
            command.extend(['--latency-steps',str(args.latency_steps)])
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
    errors = 0
    for future in as_completed([executor.submit(episode,seed) for seed in args.seeds]):
        result = future.result()
        errors += bool(result.get('error'))
        print(json.dumps(result),flush=True)
if args.final:
    check()
raise SystemExit(1 if errors else 0)
