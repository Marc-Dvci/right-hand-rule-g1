"""Count only fully written episode reports and ZIP-complete traces."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]


def progress(directory):
    strata=defaultdict(lambda:dict(completed=0,exits=0,checker_stops=0,actual_limit_findings=0))
    failures=[]
    for path in directory.rglob('report.json'):
        try:
            report=json.loads(path.read_text())
        except (OSError,json.JSONDecodeError):
            continue
        if 'layout_id' not in report or not zipfile.is_zipfile(path.parent/'trace.npz'):
            continue
        key=f'{report["mode"]}/{report["nominal_command_latency_ms"]}ms'
        row=strata[key]
        row['completed']+=1
        row['exits']+=int(report['exited'])
        row['checker_stops']+=int(bool(report['reason']))
        row['actual_limit_findings']+=sum(len(w.get('limits',[])) for w in report['warnings'].values())
        if not report['exited']:
            failures.append(dict(seed=report['seed'],layout=report['layout_id'],stratum=key,reason=report['reason']))
    return dict(directory=directory.name,strata=dict(strata),failures=failures,final_results=(directory/'outcomes.json').exists())


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('directories',nargs='+',type=Path)
    a=p.parse_args()
    print(json.dumps([progress(d) for d in a.directories],indent=2))
