"""Isolated episodes on explicit topologies, with strict final/development split."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import argparse
import json
import random
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.protocol import validate_cohort
p=argparse.ArgumentParser()
p.add_argument('--name',required=True)
p.add_argument('--control-config',type=Path,required=True)
p.add_argument('--parameters',type=Path,default=ROOT/'config/navigation.json')
p.add_argument('--layouts',nargs='+',type=int)
p.add_argument('--count',type=int,default=12)
p.add_argument('--delays',nargs='+',type=int,choices=(0,1,2),default=[0,1,2])
p.add_argument('--mode',default='navigate')
p.add_argument('--workers',type=int,default=4)
p.add_argument('--final',action='store_true')
a=p.parse_args()
if not a.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.name):
    raise ValueError('Use a simple unique evidence name')
protocol=json.loads((ROOT/'review/evaluation_v2_protocol.json').read_text())
output=ROOT/'evidence/catalog'/a.name
if output.exists():
    raise SystemExit('Refusing to replace existing cohort evidence')
if not 1<=a.workers<=6:
    raise ValueError('Use 1 to 6 isolated single-threaded workers')
if a.final:
    sys.path.insert(0,str(ROOT))
    from tools.freeze_v2 import check
    frozen=check()
    if a.control_config.resolve()!=(ROOT/'config/control.json').resolve() or a.parameters.resolve()!=(ROOT/'config/navigation.json').resolve():
        raise ValueError('Final evaluation must use selected frozen configuration')
    ids=protocol['holdout_topologies']
    seeds=protocol['holdout_seeds']
    if a.mode!='navigate':
        ids,seeds=ids[:protocol['controls']['matched_first_n_seeds']],seeds[:protocol['controls']['matched_first_n_seeds']]
else:
    ids=a.layouts or random.Random(119021).sample(protocol['development_topologies'],a.count)
    seeds=[12000+index for index in ids]
validate_cohort(protocol,layouts=ids,delays=a.delays,mode=a.mode,final=a.final)
output.mkdir(parents=True)
manifest=dict(final=a.final,mode=a.mode,layouts=ids,seeds=seeds,delays=a.delays,
    parameters=json.loads(a.parameters.read_text()),control=json.loads(a.control_config.read_text()))
(output/'cohort.json').write_text(json.dumps(manifest,indent=2)+'\n')
if a.final:
    (output/'freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')


def episode(case):
    layout,seed,delay=case
    directory=output/f'{a.mode}-layout{layout}-s{seed}-d{delay}'
    directory.mkdir()
    command=[sys.executable,str(ROOT/'harness/catalog_evaluate.py'),'--layout-id',str(layout),
        '--seed',str(seed),'--seconds',str(protocol['time_limit_seconds']),'--mode',a.mode,'--delay',str(delay),
        '--control-config',str(a.control_config.resolve()),'--parameters',str(a.parameters.resolve()),'--output',str(directory)]
    if a.final:
        command.append('--final')
    with (directory/'run.log').open('w') as log:
        proc=subprocess.run(command,stdout=log,stderr=log)
    if proc.returncode:
        return dict(layout=layout,seed=seed,delay=delay,error=True)
    r=json.loads((directory/'report.json').read_text())
    hard=sum(len(w.get('limits',[])) for w in r['warnings'].values())
    return dict(layout=layout,seed=seed,delay=delay,exited=r['exited'],reason=r['reason'],hard=hard,
        seconds=round(r['seconds'],2),thrash=round(r['thrash_peak'],3),peak_force=round(r['touch_metrics']['peak_500hz_hand_force_n'],2))


rows=[]
with ThreadPoolExecutor(max_workers=a.workers) as pool:
    for future in as_completed([pool.submit(episode,(layout,seed,delay)) for layout,seed in zip(ids,seeds) for delay in a.delays]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
if a.final:
    check()
(output/'outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(1 if any(row.get('error') for row in rows) else 0)
