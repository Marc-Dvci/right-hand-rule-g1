"""Independently qualify all declared V2 topology/delay episodes and controls."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.freeze_v2 import check
from harness.maze_catalog import wall_segments
from harness.randomization import parameters as draw_parameters
from harness.scoring import score_trajectory
from tools.check_native_episode import REQUIRED_CHECKS


def sha256(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            value.update(chunk)
    return value.hexdigest()


def source_digest():
    files=sorted((ROOT/'policy').glob('*.py'))+sorted((ROOT/'policy/models').glob('*.json'))+sorted((ROOT/'policy/models').glob('*.npz'))
    result=hashlib.sha256()
    for path in files:
        result.update(path.relative_to(ROOT).as_posix().encode())
        result.update(path.read_bytes())
    return result.hexdigest()


def audit(directories, output, require_controls=True):
    frozen=check()
    protocol=frozen['protocol']
    freeze_hash=sha256(ROOT/'evaluation/frozen-v2.json')
    controller_hash=source_digest()
    navigation=json.loads((ROOT/'config/navigation.json').read_text())
    control=json.loads((ROOT/'config/control.json').read_text())
    deployment=json.loads((ROOT/'config/deployment.json').read_text())
    mapping=dict(zip(protocol['holdout_seeds'],protocol['holdout_topologies']))
    records={}
    for directory in directories:
        for path in sorted(directory.rglob('report.json')):
            report=json.loads(path.read_text())
            if report.get('split')!='geometry_holdout':
                raise ValueError('Non-holdout report in final evidence: '+str(path))
            seed,delay,mode=report['seed'],report['nominal_command_latency_ms'],report['mode']
            key=(mode,delay,seed)
            if key in records:
                raise ValueError('Duplicate final episode: '+str(key))
            if seed not in mapping or report['layout_id']!=mapping[seed]:
                raise ValueError('Wrong declared seed/topology pair')
            if report['controller_sha256']!=controller_hash or report['freeze_sha256']!=freeze_hash:
                raise ValueError('Source/freeze mismatch')
            if report['controller_parameters']!=navigation or report['control_parameters']!=control:
                raise ValueError('Selected configuration mismatch')
            if report['evaluation_sha256']!=frozen['files']['harness/evaluate.py']:
                raise ValueError('Evaluator source mismatch')
            if report['protocol_sha256']!=frozen['files']['review/evaluation_v2_protocol.json']:
                raise ValueError('Evaluation protocol mismatch')
            if set(report['scene_generator_sha256'])!={'harness/catalog_evaluate.py','harness/maze_catalog.py'}:
                raise ValueError('Incomplete scene generator provenance')
            for name,value in report['scene_generator_sha256'].items():
                if value!=frozen['files'][name]:
                    raise ValueError('Scene generator mismatch')
            if report.get('safety_checks') is not True or report.get('control_path')!='submission':
                raise ValueError('Primary checker path disabled')
            if any(report.get('checks',{}).get(name) is not True for name in REQUIRED_CHECKS):
                raise ValueError('Required primary check disabled')
            if report['transport_config']!=deployment or not report['transport_adapter']:
                raise ValueError('Deployment timing configuration mismatch')
            expected=draw_parameters(seed)
            expected['command_latency_steps']=delay//20
            if report['randomized_parameters']!=expected or report.get('robustness_stress'):
                raise ValueError('Primary randomization distribution mismatch')
            if report.get('mujoco_version')!='3.3.7' or report.get('numpy_version')!='2.5.2':
                raise ValueError('Evaluation dependency mismatch')
            width=report['corridor_width']
            spec=report['scene_specification']
            expected_exit=dict(axis=0,value=2.5*width+.25,sign=1,min_y=1.5*width,max_y=2.5*width)
            if width!=expected['corridor_width'] or spec['exit']!=expected_exit:
                raise ValueError('Width or designated exit differs from protocol')
            if not np.array_equal(np.asarray(spec['walls']),np.asarray(wall_segments(mapping[seed],width))):
                raise ValueError('Actual geometry differs from declared topology')
            with np.load(path.parent/'trace.npz',allow_pickle=False) as archive:
                time,qpos=archive['time'],archive['qpos']
                if time[-1]>protocol['time_limit_seconds']+.021:
                    raise ValueError('Episode exceeded declared time budget')
                entrance=min(point[0] for wall in spec['walls'] for point in wall)-.15
                score=score_trajectory(time,qpos,spec['exit'],entrance)
                if score['exited']!=report['exited'] or (score['wrong_exit_time'] is not None)!=report['wrong_exit']:
                    raise ValueError('Independent trajectory score mismatch')
                if len(time)!=report['policy_calls'] or archive['q'].shape!=(len(time),29):
                    raise ValueError('Incomplete trajectory coverage')
                if not np.isfinite(archive['q']).all():
                    raise ValueError('Nonfinite sensor record')
                minimum_height=float(qpos[:,2].min())
            hard=[v for w in report['warnings'].values() for v in w.get('limits',[])]
            records[key]=dict(mode=mode,delay_ms=delay,seed=seed,layout=report['layout_id'],exited=score['exited'],
                exit_time=score['exit_time'],seconds=report['seconds'],reason=report['reason'],hard_findings=len(hard),
                minimum_base_height=minimum_height,thrash=report['thrash_peak'],
                submitted_coverage=report.get('policy_handoff_at_secs') is not None and report['seconds']-report['policy_handoff_at_secs']>=10 and report.get('commands',0)>0,
                peak_hand_resultant_n=report['touch_metrics']['peak_500hz_hand_force_n'],
                peak_hand_load_n=max(report['contact_loads']['peak_sum_contact_magnitudes_n']),
                peak_nonhand_wall_load_n=report['contact_loads']['peak_nonhand_wall_sum_n'],
                calibration=report.get('command_age_calibration'),
                report_path=path.relative_to(ROOT).as_posix(),report_sha256=sha256(path),
                trace_sha256=sha256(path.parent/'trace.npz'))
    expected_keys={('navigate',delay,seed) for delay in protocol['command_delays_ms'] for seed in mapping}
    if require_controls:
        expected_keys|={(mode,delay,seed) for mode in protocol['controls']['modes']
            for delay in protocol['command_delays_ms'] for seed in protocol['holdout_seeds'][:protocol['controls']['matched_first_n_seeds']]}
    if set(records)!=expected_keys:
        raise ValueError(f'Final episode inventory differs: {len(expected_keys-set(records))} missing, {len(set(records)-expected_keys)} extra')
    strata=[]
    for mode,delay in sorted({(mode,delay) for mode,delay,seed in records}):
        rows=[r for (m,d,s),r in records.items() if (m,d)==(mode,delay)]
        count=len(rows)
        exits=sum(r['exited'] for r in rows)
        stops=sum(bool(r['reason']) for r in rows)
        findings=sum(r['hard_findings'] for r in rows)
        incomplete=sum(not r['submitted_coverage'] for r in rows)
        strata.append(dict(mode=mode,delay_ms=delay,episodes=count,distinct_topologies=len({r['layout'] for r in rows}),
            exits=exits,checker_stops=stops,actual_limit_findings=findings,
            insufficient_submitted_control=incomplete,
            peak_thrash=max(r['thrash'] for r in rows),
            median_success_seconds=float(np.median([r['seconds'] for r in rows if r['exited']])) if exits else None,
            peak_hand_load_n=max(r['peak_hand_load_n'] for r in rows),
            peak_nonhand_wall_load_n=max(r['peak_nonhand_wall_load_n'] for r in rows),
            gate_passed=(exits/count>=protocol['per_delay_target_exit_rate'] and stops==0 and findings==0 and incomplete==0) if mode=='navigate' else None))
    result=dict(scope='100 distinct previously held-out 3x3 topologies; 600-second limit; per-delay strata.',
        controller_sha256=controller_hash,freeze_sha256=freeze_hash,all_independent_scores_match=True,
        all_seeds_layouts_settings_and_randomization_match=True,
        primary_gate_passed=all(s['gate_passed'] for s in strata if s['mode']=='navigate'),
        controls_complete=require_controls,strata=strata,rows=list(records.values()),hardware_authorization=False)
    check()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('directories',nargs='+',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/v2/final-audit.json')
    parser.add_argument('--primary-only',action='store_true')
    args=parser.parse_args()
    result=audit(args.directories,args.output,require_controls=not args.primary_only)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    raise SystemExit(0 if result['primary_gate_passed'] else 2)
