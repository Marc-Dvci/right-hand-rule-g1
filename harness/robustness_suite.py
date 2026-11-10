"""Declared physical perturbation suite; all failures remain in the evidence."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import subprocess
import sys
import argparse
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--name',default='development-20261110')
p.add_argument('--workers',type=int,default=2,choices=range(1,5))
a=p.parse_args()
if not a.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.name):
    raise ValueError('Use a simple unique evidence name')
target=ROOT/'evidence/robustness'/a.name
target.mkdir(parents=True,exist_ok=False)
profiles={'damping08':{'velocity_damping_scale':.8},'damping12':{'velocity_damping_scale':1.2},
    'push_left':{'push':dict(start=15.,duration=.25,body='pelvis',force=[0.,10.,0.])},
    'push_right':{'push':dict(start=15.,duration=.25,body='pelvis',force=[0.,-10.,0.])}}
for name,profile in profiles.items():
    (target/f'{name}.json').write_text(json.dumps(profile,indent=2)+'\n')
cases=[(name,seed,delay) for name in profiles for seed in (0,17) for delay in (0,2)]
(target/'protocol.json').write_text(json.dumps(dict(cases=cases,scene='wall',seconds=120,randomize=True,
    profiles=profiles,control=json.loads((ROOT/'config/control.json').read_text()),
    scope='Separate stress suite, not the primary distribution. Damping changes effective actuator velocity bias; '
          'pushes use the canonical plant hook. Checks and contact properties are unchanged.'),indent=2)+'\n')


def episode(case):
    name,seed,delay=case
    output=target/f'{name}-s{seed}-d{delay}'
    output.mkdir()
    command=[sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','wall','--seed',str(seed),
        '--seconds','120','--randomize','--transport','--latency-steps',str(delay),
        '--robustness-config',str(target/f'{name}.json'),'--output',str(output)]
    with (output/'run.log').open('w') as log:
        process=subprocess.run(command,stdout=log,stderr=log)
    if process.returncode:
        return dict(case=case,error=True)
    r=json.loads((output/'report.json').read_text())
    return dict(case=case,exited=r['exited'],reason=r['reason'],seconds=r['seconds'],
        hard=sum(len(w.get('limits',[])) for w in r['warnings'].values()),thrash=r['thrash_peak'],
        calibration=r['command_age_calibration'],loads=r['contact_loads'])


rows=[]
with ThreadPoolExecutor(max_workers=a.workers) as pool:
    for future in as_completed([pool.submit(episode,c) for c in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k!='loads'}),flush=True)
(target/'outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(int(any(r.get('error') for r in rows)))
