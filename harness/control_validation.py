"""Validate promising development settings across timing, turns and contact."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'evidence/stability/control-validation-v2'
target.mkdir(parents=True,exist_ok=True)


def episode(case):
    index,delay,scene=case
    folder=target/f'trial{index:03d}-delay{delay}-{scene}'
    folder.mkdir(exist_ok=True)
    config=ROOT/f'evidence/stability/predict-filter-v2/trial-{index:03d}/control.json'
    with (folder/'run.log').open('w') as log:
        result=subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene',scene,
            '--mode','walk_test' if scene=='flat' else 'navigate','--seconds','60' if scene=='flat' else '400',
            '--transport','--latency-steps',str(delay),'--control-config',str(config),
            '--parameters',str(ROOT/'config/navigation.json'),'--output',str(folder)],stdout=log,stderr=log)
    if result.returncode:
        return dict(case=case,error=True)
    r=json.loads((folder/'report.json').read_text())
    hard=[v for w in r['warnings'].values() for v in w.get('limits',[])]
    return dict(case=case,status=r['status'],reason=r['reason'],seconds=r['seconds'],exited=r['exited'],
                thrash=r['thrash_peak'],hard=len(hard),diagnostics=len(r['warnings']),
                peak_force=r['touch_metrics']['peak_500hz_hand_force_n'])


cases=[(index,delay,scene) for index in (3,9,11) for delay in (0,1,2) for scene in ('flat','maze')]
rows=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(episode,c) for c in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
