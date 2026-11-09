"""Create the compact, reviewable evidence included directly in the repository."""
import json
from pathlib import Path
import shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'evaluation/results'
out.mkdir(parents=True,exist_ok=True)
summary=json.loads((ROOT/'reports/final-nominal/summary.json').read_text())
native=json.loads((ROOT/'reports/native-summary.json').read_text())
comparisons={name:json.loads((ROOT/f'reports/comparisons/{name}/summary.json').read_text())
             for name in ('neutral','touch_off','touch_shuffled','map_only','latency-20ms','latency-40ms')}
for source,name in (
    ('reports/final-nominal/summary.json','summary.json'),('reports/native-summary.json','native-summary.json'),
    ('reports/final-audit.json','final-audit.json'),('reports/hero/metrics.json','hero-metrics.json'),
    ('reports/final-nominal/cohort.svg','cohort.svg'),('reports/hero/force-and-touch-map.svg','force-and-touch-map.svg')):
    shutil.copyfile(ROOT/source,out/name)
(out/'comparisons.json').write_text(json.dumps(comparisons,indent=2)+'\n')
lines=['# Measured results','',
    f'Frozen controller: `{summary["controller_hashes"][0]}`. Primary split: **{summary["exits"]}/{summary["episodes"]} exits**, '
    f'{summary["falls"]} falls, {summary["checker_stops"]} checker stops, {summary["episodes_with_hard_findings"]} episodes with actual limit findings. '
    f'Median successful time {summary["median_success_seconds"]:.2f} s; peak thrash {summary["peak_thrash"]:.6f} / 1.5.','',
    f'There are {summary["unique_topologies"]} distinct maze topologies across 100 randomized episodes. '
    'All seed draws, raw per-episode results, hashes and an independent full-trace audit are preserved.','',
    '| Comparison | Exits | Checker stops | Episodes with actual limit findings |','|---|---:|---:|---:|']
names=dict(neutral='Neutral',touch_off='Touch off',touch_shuffled='Touch delayed 3.4 s',map_only='True map + basic dead reckoning',
           **{'latency-20ms':'Additional 20 ms command delay','latency-40ms':'Additional 40 ms command delay'})
for name,r in comparisons.items():
    lines.append(f'| {names[name]} | {r["exits"]}/{r["episodes"]} | {r["checker_stops"]} | {r["episodes_with_hard_findings"]} |')
matched=sum(r['exited'] for r in summary['rows'] if 26111500<=r['seed']<=26111509)
lines+=['',f'The complete touch controller exited {matched}/10 on the matched control seeds. '
        'Controls use the first ten primary seeds; command-delay stresses use the first five. '
        'The map baseline deliberately receives the true static map; it is never deployed. '
        'The delayed-touch control is a fixed delay, not random shuffling.','',
        '## All six primary navigation failures','', '| Seed | Final state | Simulated seconds |','|---|---|---:|']
for row in summary['rows']:
    if not row['exited']:
        with np.load((ROOT/row['report_path']).parent/'trace.npz',allow_pickle=False) as z:
            state=str(z['state'][-1])
        lines.append(f'| {row["seed"]} | {state} | {row["seconds"]:.2f} |')
lines+=['','No failed episode is replaced or removed.','', '## Native ARM64','',
    f'Exact archive SHA-256: `{native["image_sha256"]}`. '
    f'Standard {native["standard_passes"]}/3; task {native["task_passes"]}/3; designated exits {native["task_exits"]}/3. '
    f'Peak native thrash: {native["native_peak_thrash"]:.6f}.','',
    '| Task repeat | Exit time (s) | Checker |','|---|---:|---|']
for row in native['rows']:
    if row['scene']=='task':
        lines.append(f'| {row["repeat"]} | {row["exit_time"]:.6f} | {row["builder_status"]} |')
lines+=['','Task runs disclose the post-run report-RPC-only timeout fix. Canonical vendor files, active deadlines, '
        'physics and checks are unchanged. [Raw workflow](https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42656538931).','',
        '## Every counterfactual start','', '| Scene | Start | Outcome | Handoff |','|---|---|---|---|']
for row in sorted(native['counterfactuals'],key=lambda r:(r['scene'],r['pose'])):
    outcome=row['reason'] or row['status']
    if row['reason']=='no_report':
        outcome='Rejected: initial penetration; no report'
    handoff=f'{row["handoff"]:.2f} s' if row['handoff'] is not None else 'none'
    lines.append(f'| {row["scene"]} | {row["pose"]} | {outcome} | {handoff} |')
lines+=['','Both suites return `review_required`; floor-pose violations and errors are not claimed as passes.','',
    '## Force and physical transfer','',
    f'The worst raw 500 Hz hand-contact impulse in the primary split is **{summary["peak_500hz_hand_force_n"]:.2f} N**. '
    'The hero force-vector RMS is 1.883 N (26.0% of target), with 0.925 m endpoint odometry error. '
    'The original 20 N peak-force and 25% force-error gates are not met. No hardware authorization or delay-robustness claim is made. '
    'See [the implementation audit](../../PROJECT_AUDIT.md) and [hardware qualification notes](../../HARDWARE_ATTEMPT.md).','']
(out/'RESULTS.md').write_text('\n'.join(lines))
print('Published compact evidence:',out)
