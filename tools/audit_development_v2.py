"""Audit the fresh selected-controller development cohort and separate stresses."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json
import inspect
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_v2 import source_digest,sha256
from harness.scoring import score_trajectory
from harness.maze_catalog import wall_segments
from tools.check_native_episode import REQUIRED_CHECKS
from container.timing import TimedPolicy


def record(path):
    report=json.loads(path.read_text())
    if report['controller_sha256']!=source_digest():
        raise ValueError('Mixed development policy versions')
    for field,name in (('controller_parameters','navigation'),('control_parameters','control'),('transport_config','deployment')):
        actual=report[field]
        if field=='transport_config' and actual is None and report['transport_adapter']:
            # The stress CLI omitted overrides; TimedPolicy applies its frozen
            # constructor defaults. Preserve the original report unchanged.
            actual={k:v.default for k,v in inspect.signature(TimedPolicy).parameters.items() if k!='controller'}
        if actual!=json.loads((ROOT/f'config/{name}.json').read_text()):
            raise ValueError('Development settings differ from selected configuration')
    if report.get('control_path')!='submission' or report.get('safety_checks') is not True or any(report['checks'].get(c) is not True for c in REQUIRED_CHECKS):
        raise ValueError('Required checks disabled')
    if report['evaluation_sha256']!=sha256(ROOT/'harness/evaluate.py'):
        raise ValueError('Mixed development evaluator versions')
    spec=report['scene_specification']
    entrance=min(p[0] for wall in spec['walls'] for p in wall)-.15
    # Wall stress uses no designated entrance. The maze evaluator does.
    with np.load(path.parent/'trace.npz',allow_pickle=False) as trace:
        score=score_trajectory(trace['time'],trace['qpos'],spec['exit'],entrance if report.get('layout_id') is not None else None)
        if score['exited']!=report['exited'] or len(trace['time'])!=report['policy_calls']:
            raise ValueError('Development score or coverage mismatch')
    hard=sum(len(w.get('limits',[])) for w in report['warnings'].values())
    return report,dict(seed=report['seed'],layout=report.get('layout_id'),delay_ms=report['nominal_command_latency_ms'],
        exited=report['exited'],seconds=report['seconds'],reason=report['reason'],actual_limit_findings=hard,
        peak_thrash=report['thrash_peak'],calibration=report['command_age_calibration'],
        peak_hand_load_n=max(report['contact_loads']['peak_sum_contact_magnitudes_n']),
        peak_nonhand_wall_load_n=report['contact_loads']['peak_nonhand_wall_sum_n'],
        report_path=path.relative_to(ROOT).as_posix(),report_sha256=sha256(path),trace_sha256=sha256(path.parent/'trace.npz'))


def summarize(rows,scope):
    return dict(scope=scope,episodes=len(rows),exits=sum(r['exited'] for r in rows),
        checker_stops=sum(bool(r['reason']) for r in rows),actual_limit_findings=sum(r['actual_limit_findings'] for r in rows),
        source_sha256=source_digest(),independent_scores_match=True,rows=rows)


def main():
    protocol=json.loads((ROOT/'review/evaluation_v2_protocol.json').read_text())
    base=ROOT/'evidence/catalog/selected-recovery-development-all-delays-20261110'
    rows=[]
    seen=set()
    for path in sorted(base.rglob('report.json')):
        report,row=record(path)
        layout=report['layout_id']
        key=(layout,row['delay_ms'])
        if key in seen or report['seed']!=12000+layout or report['split']!='development_geometry':
            raise ValueError('Duplicate or incorrect development episode')
        if not np.array_equal(report['scene_specification']['walls'],wall_segments(layout,report['corridor_width'])):
            raise ValueError('Development geometry differs')
        seen.add(key)
        rows.append(row)
    expected={(layout,delay) for layout in protocol['development_topologies'] for delay in (0,20,40)}
    if seen!=expected:
        raise ValueError(f'Development inventory differs: {len(expected-seen)} missing')
    result=summarize(rows,'Fresh selected V2: all 92 development topologies at each delay, 600 seconds. These are tuning data, not the geometry holdout.')
    result['strata']=[summarize([r for r in rows if r['delay_ms']==delay],f'{delay} ms') for delay in (0,20,40)]
    output=ROOT/'reports/v2'
    output.mkdir(parents=True,exist_ok=True)
    (output/'development-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    stress_base=ROOT/'evidence/robustness/selected-v2-stresses-20261110'
    stresses=[]
    seen=set()
    for path in sorted(stress_base.rglob('report.json')):
        report,row=record(path)
        key=(path.parent.name,row['seed'],row['delay_ms'])
        if key in seen or not report['robustness_stress']:
            raise ValueError('Invalid separate stress record')
        seen.add(key)
        row['stress']=path.parent.name
        row['stress_specification']=report['robustness_stress']
        stresses.append(row)
    declared=json.loads((stress_base/'protocol.json').read_text())
    expected={(f'{name}-s{seed}-d{delay}',seed,delay*20) for name,seed,delay in declared['cases']}
    if seen!=expected or len(stresses)!=16:
        raise ValueError('Incomplete separate stress inventory')
    stress=summarize(stresses,'Separate straight-wall stresses: effective damping 0.8/1.2 and +/-10 N lateral pelvis force for 0.25 s; two seeds at 0/40 ms.')
    (output/'stress-summary.json').write_text(json.dumps(stress,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','strata')},indent=2))
    print(json.dumps({k:v for k,v in stress.items() if k!='rows'},indent=2))


if __name__=='__main__':
    main()
