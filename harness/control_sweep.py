"""Predeclared development tests of prediction/filtering under two-frame delay."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--name',default='predict-filter-v2')
p.add_argument('--seconds',type=int,default=35)
p.add_argument('--delay',type=int,default=2)
a=p.parse_args()
target=ROOT/'evidence/stability'/a.name
target.mkdir(parents=True,exist_ok=True)


def episode(settings):
    index,control=settings
    folder=target/f'trial-{index:03d}'
    folder.mkdir(exist_ok=True)
    (folder/'control.json').write_text(json.dumps(control)+'\n')
    with (folder/'run.log').open('w') as log:
        result=subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','flat','--mode','walk_test',
            '--seconds',str(a.seconds),'--transport','--latency-steps',str(a.delay),'--control-config',str(folder/'control.json'),
            '--parameters',str(ROOT/'config/navigation.json'),'--output',str(folder)],stdout=log,stderr=log)
    if result.returncode:
        return dict(index=index,control=control,error=True)
    r=json.loads((folder/'report.json').read_text())
    return dict(index=index,control=control,status=r['status'],reason=r['reason'],seconds=r['seconds'],
                thrash=r['thrash_peak'],warnings=r['warnings'],position=r['final_position'])


settings=[dict(waist_kp=kp,waist_gravity=g,walker_prediction=prediction,action_filter=alpha,walk_blend=.04)
          for kp,g in ((190,0),(40,1)) for prediction in (0.,.02,.04) for alpha in (.5,1.)]
rows=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(episode,s) for s in enumerate(settings)]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
