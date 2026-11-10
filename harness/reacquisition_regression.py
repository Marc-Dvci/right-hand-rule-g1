"""Retest every ARC-timeout development failure with bounded wall reacquisition."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
original=ROOT/'evidence/catalog/baseline05-all-development-delay40-20261110'
target=ROOT/'evidence/development/arc-reacquisition-20261110'
target.mkdir(parents=True,exist_ok=False)
reports=[json.loads(p.read_text()) for p in original.glob('*/report.json')]
cases=sorted((r['layout_id'],r['seed']) for r in reports if not r['exited'])
if len(reports)!=92 or len(cases)!=21:
    raise ValueError('The original complete development cohort is required')
(target/'protocol.json').write_text(json.dumps(dict(cases=cases,seconds=600,delay_ms=40,
    purpose='Only replace ARC timeout; separately replay successful sensor streams to require unchanged commands.'),indent=2)+'\n')


def episode(case):
    layout,seed=case
    output=target/f'layout{layout}-seed{seed}'
    output.mkdir()
    command=[sys.executable,str(ROOT/'harness/catalog_evaluate.py'),'--layout-id',str(layout),'--seed',str(seed),
        '--seconds','600','--delay','2','--control-config',str(ROOT/'config/control.json'),'--output',str(output)]
    with (output/'run.log').open('w') as log:
        process=subprocess.run(command,stdout=log,stderr=log)
    if process.returncode:
        return dict(layout=layout,error=True)
    r=json.loads((output/'report.json').read_text())
    return dict(layout=layout,exited=r['exited'],wrong_exit=r['wrong_exit'],reason=r['reason'],seconds=r['seconds'],
        hard=sum(len(w.get('limits',[])) for w in r['warnings'].values()),thrash=r['thrash_peak'],
        recoveries=sum(bool(e.get('recovery')) for e in r['controller_events']))


rows=[]
with ThreadPoolExecutor(max_workers=6) as pool:
    for future in as_completed([pool.submit(episode,c) for c in cases]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(int(any(r.get('error') for r in rows)))
