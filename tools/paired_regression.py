"""Independently re-score matched retired episodes; never treat them as holdouts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.scoring import score_trajectory


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def cohort(directory):
    rows={}
    for path in sorted(directory.glob('*/report.json')):
        report=json.loads(path.read_text())
        trace=path.parent/'trace.npz'
        if not zipfile.is_zipfile(trace):
            raise ValueError('Incomplete trace: '+str(trace))
        with np.load(trace,allow_pickle=False) as archive:
            time,qpos=archive['time'],archive['qpos']
            spec=report['scene_specification']
            entrance=min(point[0] for wall in spec['walls'] for point in wall)-.15
            score=score_trajectory(time,qpos,spec['exit'],entrance)
            if score['exited']!=report['exited']:
                raise ValueError('Independent score mismatch: '+str(path))
            minimum_height=float(qpos[:,2].min())
        seed=report['seed']
        if seed in rows:
            raise ValueError('Duplicate seed')
        rows[seed]=dict(seed=seed,exited=score['exited'],seconds=report['seconds'],reason=report['reason'],
            wrong_exit=report['wrong_exit'],controller_sha256=report['controller_sha256'],
            parameters=report['controller_parameters'],control=report.get('control_parameters'),
            randomization=report['randomized_parameters'],scene_sha256=report['scene_sha256'],
            thrash=report['thrash_peak'],peak_hand_force_n=report['touch_metrics']['peak_500hz_hand_force_n'],
            hard=sum(len(w.get('limits',[])) for w in report['warnings'].values()),
            minimum_height=minimum_height,report_sha256=sha256(path),trace_sha256=sha256(trace))
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--v1',type=Path,required=True)
    p.add_argument('--v2',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    old,new=cohort(a.v1),cohort(a.v2)
    expected=set(range(26111500,26111600))
    if set(old)!=expected or set(new)!=expected:
        raise ValueError('Paired 100-episode inventory is incomplete')
    for seed in expected:
        for key in ('randomization','parameters','scene_sha256'):
            if old[seed][key]!=new[seed][key]:
                raise ValueError(f'Unmatched {key} for seed {seed}')
    fixed=[s for s in sorted(expected) if new[s]['exited'] and not old[s]['exited']]
    regressed=[s for s in sorted(expected) if old[s]['exited'] and not new[s]['exited']]
    discordant=len(fixed)+len(regressed)
    pvalue=min(1.,2*sum(math.comb(discordant,i) for i in range(min(len(fixed),len(regressed))+1))/2**discordant) if discordant else 1.
    def metrics(rows):
        return dict(exits=sum(r['exited'] for r in rows.values()),stops=sum(bool(r['reason']) for r in rows.values()),
            actual_findings=sum(r['hard'] for r in rows.values()),peak_thrash=max(r['thrash'] for r in rows.values()),
            peak_hand_force_n=max(r['peak_hand_force_n'] for r in rows.values()),
            median_success_seconds=float(np.median([r['seconds'] for r in rows.values() if r['exited']])),
            controller_hashes=sorted({r['controller_sha256'] for r in rows.values()}))
    result=dict(episodes=100,scope='Retired development regression over 14 legacy topologies; not a new holdout.',
        independently_scored=True,all_randomization_settings_and_scenes_match=True,
        v1=metrics(old),turn_only=metrics(new),fixed=fixed,regressed=regressed,
        mcnemar_exact_two_sided_pvalue=pvalue,
        interpretation='Observed paired gain; this sample does not establish a statistically significant gain at 5%. '
                       'Episode-level geometry dependence and repeated development use limit generalization.',
        rows=[dict(seed=s,v1=old[s],turn_only=new[s]) for s in sorted(expected)])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
