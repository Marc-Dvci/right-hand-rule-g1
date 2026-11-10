"""Test causal command/force time alignment on retired delayed-control failures."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
target = ROOT/'evidence/development/force-alignment-20261110'
target.mkdir(parents=True, exist_ok=False)
candidate = json.loads((ROOT/'review/candidates/yaw-stable-development.json').read_text())
for age in (0, 1, 2):
    (target/f'age-{age}.json').write_text(json.dumps(dict(candidate, force_command_age_steps=age), indent=2)+'\n')
cases = [(age, seed) for age in (0, 1, 2) for seed in (0, 5, 13)]
(target/'protocol.json').write_text(json.dumps(dict(cases=cases, delay_ms=40, seconds=400,
    randomize=True, purpose='Applied-command estimate from local history; no extra simulator observations'), indent=2)+'\n')


def episode(case):
    age, seed = case
    output = target/f'age{age}-seed{seed}'
    output.mkdir()
    command = [sys.executable, str(ROOT/'harness/evaluate.py'), '--scene', 'maze', '--seed', str(seed),
        '--seconds', '400', '--randomize', '--transport', '--latency-steps', '2',
        '--control-config', str(target/f'age-{age}.json'), '--output', str(output)]
    with (output/'run.log').open('w') as log:
        process = subprocess.run(command, stdout=log, stderr=log)
    if process.returncode:
        return dict(case=case, error=True)
    r = json.loads((output/'report.json').read_text())
    return dict(case=case, exited=r['exited'], wrong_exit=r['wrong_exit'], reason=r['reason'],
        seconds=r['seconds'], thrash=r['thrash_peak'],
        hard=sum(len(w.get('limits', [])) for w in r['warnings'].values()),
        peak_force_n=r['touch_metrics']['peak_500hz_hand_force_n'],
        rmse=r['touch_metrics']['bandwidth_matched_rmse_n'])


rows = []
with ThreadPoolExecutor(max_workers=3) as pool:
    for future in as_completed([pool.submit(episode, case) for case in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row), flush=True)
(target/'outcomes.json').write_text(json.dumps(rows, indent=2)+'\n')
raise SystemExit(int(any(r.get('error') for r in rows)))
