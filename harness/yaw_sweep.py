"""Development test of the measured waist-yaw oscillation under 40 ms delay."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
output = ROOT/'evidence/stability/yaw-ablation-20261110'
output.mkdir(parents=True, exist_ok=False)
configs = [dict(waist_yaw_scale=0., waist_kp=40.), dict(waist_yaw_scale=0., waist_kp=0.),
           dict(waist_yaw_scale=.5, waist_kp=40.), dict(waist_yaw_scale=0., waist_kp=80.)]
selected = json.loads((ROOT/'config/control.json').read_text())
for i, config in enumerate(configs):
    value = dict(selected, waist_gravity=1., walker_prediction=.02, walk_blend=.04, **config)
    (output/f'control-{i}.json').write_text(json.dumps(value, indent=2)+'\n')
cases = [(i, seed, delay) for i in range(4) for seed in (0, 13, 17) for delay in (0, 2)]
(output/'protocol.json').write_text(json.dumps(dict(cases=cases, scene='flat', seconds=60,
    randomize=True, purpose='Screen walking, turn and lateral phases; not maze qualification'), indent=2)+'\n')


def episode(case):
    i, seed, delay = case
    target = output/f'c{i}-s{seed}-d{delay}'
    target.mkdir()
    command = [sys.executable, str(ROOT/'harness/evaluate.py'), '--scene', 'flat', '--mode', 'walk_test',
        '--seed', str(seed), '--seconds', '60', '--randomize', '--transport', '--latency-steps', str(delay),
        '--control-config', str(output/f'control-{i}.json'), '--output', str(target)]
    with (target/'run.log').open('w') as log:
        process = subprocess.run(command, stdout=log, stderr=log)
    if process.returncode:
        return dict(case=case, error=True)
    r = json.loads((target/'report.json').read_text())
    return dict(case=case, reason=r['reason'], seconds=r['seconds'], thrash=r['thrash_peak'],
        hard=sum(len(w.get('limits', [])) for w in r['warnings'].values()), position=r['final_position'])


rows = []
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(episode, case) for case in cases]):
        row = future.result()
        rows.append(row)
        print(json.dumps(row), flush=True)
(output/'outcomes.json').write_text(json.dumps(rows, indent=2)+'\n')
raise SystemExit(int(any(r.get('error') for r in rows)))
