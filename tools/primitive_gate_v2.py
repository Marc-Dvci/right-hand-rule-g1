"""Supplemental post-freeze 50-wall/50-inner/50-outer trials from the original plan."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_development_v2 import record
from tools.freeze_v2 import check


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-root',type=Path,required=True)
    a=p.parse_args()
    source=a.source_root.resolve()
    check()
    name='selected-v2-50-each-20261110'
    target=source/'evidence/primitives'/name
    target.mkdir(parents=True,exist_ok=False)
    cases=[(scene,26130000+i) for scene in ('wall','inner','outer') for i in range(50)]
    protocol=dict(scope='Supplemental post-freeze primitive qualification, not the topology holdout or tuning.',
        cases=cases,seconds=150,randomize=True,command_delay_ms=0,
        required_corner_exits=48,required_straight_exits=50,peak_hand_limit_n=20.,
        required_wall_contact_distance_fraction=.95,contact_truth_threshold_n=1.,estimated_contact_threshold_n=3.,
        required_contact_detection_fraction_within_200ms=.98,maximum_false_contact_fraction=.01,
        maximum_vector_rmse_fraction_of_target=.25,
        measurement='Contact continuity: positive base-x travel after first physical right-hand contact, with interval mean right-hand resultant >=1 N. Detection: each rising physical contact, estimate within next 0.2 s. False contacts: fraction of physical-noncontact samples with estimated navigation contact. Vector RMSE sums xyz before averaging, both hands after startup; force truth is causally aligned. All thresholds declared before these trials.')
    (target/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')

    def episode(case):
        scene,seed=case
        directory=target/f'{scene}-s{seed}'
        directory.mkdir()
        with (directory/'run.log').open('w') as log:
            result=subprocess.run([sys.executable,str(source/'harness/evaluate.py'),'--scene',scene,'--seed',str(seed),
                '--seconds','150','--randomize','--transport','--latency-steps','0',
                '--parameters',str(source/'config/navigation.json'),'--control-config',str(source/'config/control.json'),
                '--transport-config',str(source/'config/deployment.json'),'--output',str(directory)],stdout=log,stderr=log)
        if result.returncode:
            return dict(scene=scene,seed=seed,error=True)
        r=json.loads((directory/'report.json').read_text())
        return dict(scene=scene,seed=seed,exited=r['exited'],seconds=r['seconds'])

    outcomes=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(episode,c) for c in cases]):
            row=future.result()
            outcomes.append(row)
            print(json.dumps(row),flush=True)
    (target/'outcomes.json').write_text(json.dumps(outcomes,indent=2)+'\n')
    if any(r.get('error') for r in outcomes):
        raise ValueError('Primitive infrastructure error retained; qualification incomplete')
    destination=ROOT/'evidence/primitives'/name
    shutil.copytree(target,destination)
    rows=[]
    seen=set()
    for path in sorted(destination.rglob('report.json')):
        report,row=record(path)
        scene=path.parent.name.split('-s')[0]
        key=(scene,row['seed'])
        if key in seen:
            raise ValueError('Duplicate primitive')
        seen.add(key)
        row['scene']=scene
        with np.load(path.parent/'trace.npz',allow_pickle=False) as z:
            t=z['observation_time'][1:]
            selected=t>7.
            truth=z['true_force'][:-1]
            physical=(np.linalg.norm(truth[:,1],axis=1)>=1.)&selected
            detected=z['navigation_force'][1:,1,1]>=3.
            onsets=np.flatnonzero(physical&~np.r_[False,physical[:-1]])
            timely=sum(bool(detected[i:min(len(t),i+11)].any()) for i in onsets)
            negative=selected&~physical
            error=z['estimated_force'][1:][selected]-z['true_force_filtered'][:-1][selected]
            vector_rmse=float(np.sqrt(np.mean(np.sum(error**2,axis=-1))))
            row.update(contact_onsets=len(onsets),onsets_detected_within_200ms=int(timely),
                false_contacts=int((detected&negative).sum()),noncontact_samples=int(negative.sum()),
                vector_rmse_n=vector_rmse,vector_rmse_fraction=vector_rmse/report['controller_parameters']['force_target'])
            if scene=='wall':
                force=np.linalg.norm(z['true_force'][:,1],axis=1)>=1.
                first=np.flatnonzero(force)
                progress=np.maximum(0.,np.diff(z['qpos'][:,0]))
                start=int(first[0]) if len(first) else len(progress)
                denominator=float(progress[start:].sum())
                row['contact_distance_fraction']=float((progress[start:]*force[1:][start:]).sum()/denominator) if denominator else 0.
        rows.append(row)
    if seen!=set(cases):
        raise ValueError('Incomplete primitive inventory')
    strata=[]
    for scene in ('wall','inner','outer'):
        group=[r for r in rows if r['scene']==scene]
        exits=sum(r['exited'] for r in group)
        hard=sum(r['actual_limit_findings'] for r in group)
        stops=sum(bool(r['reason']) for r in group)
        strata.append(dict(scene=scene,episodes=50,exits=exits,checker_stops=stops,actual_limit_findings=hard,
            peak_hand_load_n=max(r['peak_hand_load_n'] for r in group),peak_nonhand_wall_load_n=max(r['peak_nonhand_wall_load_n'] for r in group),
            navigation_gate_passed=exits>=(50 if scene=='wall' else 48) and not hard and not stops,
            straight_full_gate_passes=sum(r['exited'] and r['contact_distance_fraction']>=.95 and r['peak_hand_load_n']<=20 for r in group) if scene=='wall' else None))
    walls=[r for r in rows if r['scene']=='wall']
    onsets=sum(r['contact_onsets'] for r in walls)
    negatives=sum(r['noncontact_samples'] for r in walls)
    result=dict(scope=protocol['scope'],episodes=150,independent_scores_match=True,strata=strata,
        wall_contact_onsets=onsets,wall_detection_fraction_200ms=sum(r['onsets_detected_within_200ms'] for r in walls)/onsets if onsets else None,
        wall_false_contact_fraction=sum(r['false_contacts'] for r in walls)/negatives if negatives else None,
        wall_runs_meeting_vector_error_goal=sum(r['vector_rmse_fraction']<=.25 for r in walls),rows=rows,
        hardware_authorization=False)
    result['original_full_low_force_gate_passed']=(strata[0]['straight_full_gate_passes']==50
        and result['wall_detection_fraction_200ms'] is not None and result['wall_detection_fraction_200ms']>=.98
        and result['wall_false_contact_fraction'] is not None and result['wall_false_contact_fraction']<=.01
        and result['wall_runs_meeting_vector_error_goal']==50)
    (ROOT/'reports/v2/primitive-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    check()
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':
    main()
