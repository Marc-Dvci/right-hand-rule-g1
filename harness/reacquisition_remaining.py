from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'evidence/development/reacquisition-find-reorientation-20261110'
target.mkdir(parents=True,exist_ok=False)


def episode(layout):
    output=target/f'layout{layout}'
    output.mkdir()
    command=[sys.executable,str(ROOT/'harness/catalog_evaluate.py'),'--layout-id',str(layout),
        '--seed',str(12000+layout),'--seconds','600','--delay','2',
        '--control-config',str(ROOT/'config/control.json'),'--output',str(output)]
    with (output/'run.log').open('w') as log:
        process=subprocess.run(command,stdout=log,stderr=log)
    if process.returncode:
        return dict(layout=layout,error=True)
    r=json.loads((output/'report.json').read_text())
    return dict(layout=layout,exited=r['exited'],wrong_exit=r['wrong_exit'],reason=r['reason'],seconds=r['seconds'],
        hard=sum(len(w.get('limits',[])) for w in r['warnings'].values()),thrash=r['thrash_peak'],
        recoveries=sum(bool(e.get('recovery')) for e in r['controller_events']))


rows=[]
with ThreadPoolExecutor(max_workers=2) as pool:
    for future in as_completed([pool.submit(episode,layout) for layout in (60,174)]):
        row=future.result()
        rows.append(row)
        print(json.dumps(row),flush=True)
(target/'outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
