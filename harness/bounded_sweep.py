"""Development ablation for bounded PI navigation, keeping all scene physics fixed."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'evidence/development/bounded-v2'
target.mkdir(parents=True,exist_ok=True)
configs=[dict(bounded_navigation=True),
    dict(bounded_navigation=True,walker_prediction=.02,walk_blend=.04),
    dict(bounded_navigation=True,waist_kp=40,waist_gravity=1,walker_prediction=.02,walk_blend=.04),
    dict(bounded_navigation=True,waist_kp=40,waist_gravity=1,walker_prediction=.03,walk_blend=.04),
    dict(bounded_navigation=True,waist_kp=40,waist_gravity=1,walker_prediction=.04,walk_blend=.04)]
for i,config in enumerate(configs):
    (target/f'control-{i}.json').write_text(json.dumps(config,indent=2)+'\n')


def episode(case):
    index,seed,delay=case
    folder=target/f'c{index}-s{seed}-d{delay}'
    folder.mkdir(exist_ok=True)
    with (folder/'run.log').open('w') as log:
        result=subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','maze','--seed',str(seed),
            '--seconds','400','--transport','--latency-steps',str(delay),'--control-config',str(target/f'control-{index}.json'),
            '--parameters',str(ROOT/'config/navigation.json'),'--output',str(folder)],stdout=log,stderr=log)
    if result.returncode:
        return dict(case=case,error=True)
    r=json.loads((folder/'report.json').read_text())
    hard=[v for w in r['warnings'].values() for v in w.get('limits',[])]
    return dict(case=case,status=r['status'],reason=r['reason'],seconds=r['seconds'],exited=r['exited'],
        thrash=r['thrash_peak'],hard=len(hard),diagnostics=len(r['warnings']),peak_force=r['touch_metrics']['peak_500hz_hand_force_n'])


cases=[(index,seed,delay) for index in range(5) for seed in (0,4) for delay in (0,2)]
rows=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(episode,c) for c in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
