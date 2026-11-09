"""Development experiment: gravity feedforward instead of delayed high stiffness."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import argparse
import json
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--name',default='gravity-waist-v2')
p.add_argument('--seconds',type=int,default=35)
a=p.parse_args()
target=ROOT/'evidence/stability'/a.name
target.mkdir(parents=True,exist_ok=True)


def episode(settings):
    kp,gravity,delay=settings
    folder=target/f'kp{kp}-g{gravity}-delay{delay}'
    folder.mkdir(exist_ok=True)
    control=dict(waist_kp=kp,waist_kd=3.5,waist_gravity=gravity)
    (folder/'control.json').write_text(json.dumps(control)+'\n')
    with (folder/'run.log').open('w') as log:
        result=subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','flat','--mode','walk_test',
            '--seconds',str(a.seconds),'--transport','--latency-steps',str(delay),'--control-config',str(folder/'control.json'),
            '--parameters',str(ROOT/'config/navigation.json'),'--output',str(folder)],stdout=log,stderr=log)
    if result.returncode:
        return dict(settings=control,delay=delay,error=True)
    r=json.loads((folder/'report.json').read_text())
    with np.load(folder/'trace.npz') as z:
        waist=float(np.max(abs(z['q'][:,13:15])))
    return dict(settings=control,delay=delay,status=r['status'],reason=r['reason'],seconds=r['seconds'],
                thrash=r['thrash_peak'],waist_peak=waist,warnings=r['warnings'],position=r['final_position'])


settings=[(kp,g,delay) for kp,g in ((190,0),(0,1),(40,1),(80,1),(40,.7)) for delay in (0,1,2)]
rows=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(episode,s) for s in settings]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
