"""Verify sensor-only command-age identification on randomized held-still starts."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'evidence/calibration/development-20261110'
target.mkdir(parents=True,exist_ok=False)
cases=[(seed,delay) for seed in (0,1,5,13,17,18,19,26111544) for delay in (0,1,2)]
(target/'protocol.json').write_text(json.dumps(dict(cases=cases,seconds=12,mode='neutral',randomize=True,
    control=json.loads((ROOT/'review/candidates/calibrated-yaw-development.json').read_text()),
    requirement='Identify actual command-age correctly, with no checker stop or limit finding.'),indent=2)+'\n')


def episode(case):
    seed,delay=case
    output=target/f'seed{seed}-delay{delay}'
    output.mkdir()
    command=[sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','flat','--mode','neutral','--seed',str(seed),
        '--seconds','12','--randomize','--transport','--latency-steps',str(delay),
        '--control-config',str(ROOT/'review/candidates/calibrated-yaw-development.json'),'--output',str(output)]
    with (output/'run.log').open('w') as log:
        process=subprocess.run(command,stdout=log,stderr=log)
    if process.returncode:
        return dict(case=case,error=True)
    r=json.loads((output/'report.json').read_text())
    return dict(case=case,identified=r['command_age_calibration']['selected_frames'],
        calibration_error=r['command_age_calibration']['error'],confidence=r['command_age_calibration']['confidence'],
        reason=r['reason'],hard=sum(len(w.get('limits',[])) for w in r['warnings'].values()),thrash=r['thrash_peak'])


rows=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(episode,case) for case in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(int(any(r.get('error') for r in rows)))
