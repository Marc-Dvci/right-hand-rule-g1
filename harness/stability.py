"""Identify a stable waist impedance under a real one-frame command delay."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import subprocess
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
target = ROOT/'evidence/stability/waist-delay-v1'
target.mkdir(parents=True,exist_ok=True)


def evaluate(pair):
    kp,kd = pair
    output = target/f'kp{kp}-kd{kd}'
    output.mkdir(exist_ok=True)
    params = dict(command_delay=.02,waist_kp=kp,waist_kd=kd)
    (output/'transport.json').write_text(json.dumps(params,indent=2)+'\n')
    with (output/'run.log').open('w') as log:
        code = subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','flat',
            '--mode','walk_test','--seconds','25','--transport','--transport-config',str(output/'transport.json'),
            '--parameters',str(ROOT/'config/navigation.json'),'--output',str(output)],stdout=log,stderr=log).returncode
    if code:
        return dict(kp=kp,kd=kd,error=True)
    r = json.loads((output/'report.json').read_text())
    with np.load(output/'trace.npz') as z:
        waist = float(np.max(abs(z['qpos'][:,20:22])))
    return dict(kp=kp,kd=kd,status=r['status'],reason=r['reason'],seconds=r['seconds'],
                thrash=r['thrash_peak'],waist_roll_pitch=waist,position=r['final_position'],warnings=len(r['warnings']))


rows = []
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(evaluate,(kp,kd)) for kp in (0,40,80,120) for kd in (3.5,6,10)]):
        row = future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
