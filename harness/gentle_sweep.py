"""Matched navigation settings ablation, minimizing total contact loads after success."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'evidence/contact-development/gentle-navigation-20261110'
target.mkdir(parents=True,exist_ok=False)
selected=json.loads((ROOT/'config/navigation.json').read_text())
profiles={'baseline':{},'gentleA':dict(speed=.08,force_target=5.,front_threshold=3.,lost_threshold=2.2),
    'gentleB':dict(speed=.065,force_target=4.5,front_threshold=2.8,lost_threshold=2.)}
for name,changes in profiles.items():
    (target/f'{name}.json').write_text(json.dumps(dict(selected,**changes),indent=2)+'\n')
cases=[(name,scene,seed) for name in profiles for scene,seed in
       (('wall',0),('inner',0),('outer',0),('maze',0),('maze',13))]
(target/'protocol.json').write_text(json.dumps(dict(cases=cases,randomize=True,delay_ms=0,
    time_limits={'maze':600,'wall':150,'inner':150,'outer':150},
    selection='Require clean exits first; compare hand AND nonhand peaks, sustained loads and duration. '
              'Do not improve hand metrics by transferring force to another body part.'),indent=2)+'\n')


def episode(case):
    name,scene,seed=case
    output=target/f'{name}-{scene}-s{seed}'
    output.mkdir()
    command=[sys.executable,str(ROOT/'harness/evaluate.py'),'--scene',scene,'--seed',str(seed),
        '--seconds','600' if scene=='maze' else '150','--randomize','--transport','--latency-steps','0',
        '--parameters',str(target/f'{name}.json'),'--output',str(output)]
    with (output/'run.log').open('w') as log:
        process=subprocess.run(command,stdout=log,stderr=log)
    if process.returncode:
        return dict(case=case,error=True)
    r=json.loads((output/'report.json').read_text())
    return dict(case=case,exited=r['exited'],reason=r['reason'],seconds=r['seconds'],
        hard=sum(len(w.get('limits',[])) for w in r['warnings'].values()),thrash=r['thrash_peak'],
        hand_peak_n=max(r['contact_loads']['peak_sum_contact_magnitudes_n']),
        nonhand_peak_n=r['contact_loads']['peak_nonhand_wall_sum_n'],
        hand_100ms_peak_n=max(r['contact_loads']['peak_window_mean_n']['0.1']),
        nonhand_contact_seconds=r['contact_loads']['nonhand_wall_contact_seconds'])


rows=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    for future in as_completed([pool.submit(episode,c) for c in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(int(any(r.get('error') for r in rows)))
