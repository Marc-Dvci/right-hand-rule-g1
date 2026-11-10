"""Verify and independently score all portable V2 motion archives, without simulation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.scoring import score_trajectory


def check(paths,audit):
    expected={(r['mode'],r['delay_ms'],r['seed']):r for r in audit['rows']}
    seen=set()
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist())!=len(set(archive.namelist())) or archive.testzip():
                raise ValueError('Archive integrity failure')
            index=json.loads(archive.read('MOTION_INDEX.json'))
            if index['episodes']!=len(index['rows']):
                raise ValueError('Motion index count mismatch')
            for row in index['rows']:
                key=(row['mode'],row['delay_ms'],row['seed'])
                if key in seen or key not in expected:
                    raise ValueError('Duplicate or unexpected motion episode')
                seen.add(key)
                source=expected[key]
                report_data=archive.read(row['report'])
                motion=archive.read(row['replay'])
                if hashlib.sha256(report_data).hexdigest()!=source['report_sha256'] or hashlib.sha256(motion).hexdigest()!=row['replay_sha256']:
                    raise ValueError('Motion/report digest mismatch')
                if row['full_trace_sha256']!=source['trace_sha256'] or row['layout']!=source['layout']:
                    raise ValueError('Original trace/topology identity mismatch')
                report=json.loads(report_data)
                spec=report['scene_specification']
                entrance=min(p[0] for wall in spec['walls'] for p in wall)-.15
                with np.load(io.BytesIO(motion),allow_pickle=False) as trace:
                    if set(trace.files)!={'time','qpos'}:
                        raise ValueError('Unexpected motion fields')
                    score=score_trajectory(trace['time'],trace['qpos'],spec['exit'],entrance)
                if score['exited']!=source['exited'] or score['exit_time']!=source['exit_time']:
                    raise ValueError('Independent portable score differs')
    if seen!=set(expected):
        raise ValueError('Incomplete portable episode inventory')
    return dict(episodes=len(seen),all_digests_match=True,all_independent_scores_match=True,simulator_required=False)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('archives',nargs='+',type=Path)
    p.add_argument('--audit',type=Path,default=ROOT/'reports/v2/final-audit.json')
    p.add_argument('--output',type=Path,default=ROOT/'reports/v2/portable-motion-check.json')
    a=p.parse_args()
    result=check(a.archives,json.loads(a.audit.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
