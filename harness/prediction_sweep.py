from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import subprocess
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
target = ROOT/'evidence/stability/prediction-v1'
target.mkdir(parents=True,exist_ok=True)


def evaluate(pair):
    mode,pred = pair
    output = target/f'{mode}-p{pred:.3f}'
    output.mkdir(exist_ok=True)
    params = dict(waist_mode=mode,waist_kp=40,waist_kd=3.5,prediction_seconds=pred,torque_fraction=.7)
    (output/'transport.json').write_text(json.dumps(params,indent=2)+'\n')
    with (output/'run.log').open('w') as log:
        code = subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','flat','--mode','walk_test',
            '--seconds','60','--transport','--transport-config',str(output/'transport.json'),'--parameters',
            str(ROOT/'config/navigation.json'),'--output',str(output)],stdout=log,stderr=log).returncode
    if code:
        return dict(mode=mode,pred=pred,error=True)
    r = json.loads((output/'report.json').read_text())
    with np.load(output/'trace.npz') as z:
        waist = float(np.max(abs(z['qpos'][:,20:22])))
    return dict(mode=mode,prediction=pred,status=r['status'],reason=r['reason'],seconds=r['seconds'],
                thrash=r['thrash_peak'],waist_roll_pitch=waist,position=r['final_position'],warnings=r['warnings'])


rows = []
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(evaluate,(mode,pred)) for mode in ('fixed','limited') for pred in (.01,.02,.03)]):
        row = future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
