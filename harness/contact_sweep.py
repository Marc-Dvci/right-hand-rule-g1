"""Matched development ablation of arm compliance; all physics/checks unchanged."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError('Use 1 to 4 single-threaded workers')
    output = ROOT/'evidence/contact-development'/args.name
    output.mkdir(parents=True, exist_ok=False)
    selected = json.loads((ROOT/'config/control.json').read_text())
    for stiffness in (8, 12, 16, 20):
        config = dict(selected, arm_stiffness=stiffness)
        (output/f'arm-{stiffness}.json').write_text(json.dumps(config, indent=2)+'\n')
    cases = [(stiffness, scene) for stiffness in (8, 12, 16, 20) for scene in ('wall', 'inner', 'outer')]
    (output/'protocol.json').write_text(json.dumps(dict(cases=cases, seed=0, randomize=True,
        command_latency_ms=0, time_limit_seconds=180,
        selection='Use only completed development evidence. Compare exit, findings, contact loads and force peaks.'), indent=2)+'\n')

    def episode(case):
        stiffness, scene = case
        target = output/f'arm{stiffness}-{scene}'
        target.mkdir()
        command = [sys.executable, str(ROOT/'harness/evaluate.py'), '--scene', scene,
            '--seed', '0', '--seconds', '180', '--randomize', '--transport', '--latency-steps', '0',
            '--control-config', str(output/f'arm-{stiffness}.json'), '--output', str(target)]
        with (target/'run.log').open('w') as log:
            process = subprocess.run(command, stdout=log, stderr=log)
        if process.returncode:
            return dict(stiffness=stiffness, scene=scene, error=True)
        report = json.loads((target/'report.json').read_text())
        return dict(stiffness=stiffness, scene=scene, exited=report['exited'], reason=report['reason'],
            seconds=report['seconds'], hard=sum(len(w.get('limits', [])) for w in report['warnings'].values()),
            thrash=report['thrash_peak'], loads=report['contact_loads'],
            peak_resultant_n=report['touch_metrics']['peak_500hz_hand_force_n'],
            controller_sha256=report['controller_sha256'],
            report_sha256=hashlib.sha256((target/'report.json').read_bytes()).hexdigest())

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(episode, case) for case in cases]):
            row = future.result()
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != 'loads'}), flush=True)
    (output/'outcomes.json').write_text(json.dumps(rows, indent=2)+'\n')
    return int(any(row.get('error') for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
