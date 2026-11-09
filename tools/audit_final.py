"""Independently re-score all final traces and verify their frozen provenance."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.freeze_evaluation import check
from harness.scoring import score_trajectory
from harness.randomization import parameters

frozen=check()
directory=ROOT/'evidence/cohorts/final-nominal-v1'
paths=sorted(directory.glob('*/report.json'))
reports=[json.loads(p.read_text()) for p in paths]
expected=frozen['protocol']['final_seeds']
if len(reports)!=len(expected) or sorted(r['seed'] for r in reports)!=expected:
    raise SystemExit('Final seed inventory is incomplete or contains duplicates')
nav=json.loads((ROOT/'config/navigation.json').read_text())
adapter=json.loads((ROOT/'config/deployment.json').read_text())
source_files=sorted((ROOT/'policy').glob('*.py'))+sorted((ROOT/'policy/models').glob('*.json'))+sorted((ROOT/'policy/models').glob('*.npz'))
digest=hashlib.sha256()
for p in source_files:
    digest.update(str(p.relative_to(ROOT)).encode())
    digest.update(p.read_bytes())
source_digest=digest.hexdigest()
rows=[]
for p,r in zip(paths,reports):
    assert r['controller_sha256']==source_digest
    assert r['evaluation_sha256']==frozen['files']['harness/evaluate.py']
    assert r['controller_parameters']==nav and r['transport_config']==adapter
    assert r['transport_adapter'] and r['nominal_command_latency_ms']==0 and r['mode']=='navigate'
    random=parameters(r['seed'])
    random['command_latency_steps']=0
    assert r['randomized_parameters']==random
    trace=p.parent/'trace.npz'
    with np.load(trace,allow_pickle=False) as z:
        spec=r['scene_specification']
        entrance=min(point[0] for wall in spec['walls'] for point in wall)-.15
        score=score_trajectory(z['time'],z['qpos'],spec['exit'],entrance)
        assert score['exited']==r['exited'],('Independent exit score mismatch',r['seed'])
        minimum_height=float(z['qpos'][:,2].min())
        assert z['q'].shape[1]==29 and np.isfinite(z['q']).all()
    hard=[finding for warning in r['warnings'].values() for finding in warning.get('limits',[])]
    rows.append(dict(seed=r['seed'],exited=score['exited'],exit_time=score['exit_time'],reason=r['reason'],
        hard_findings=len(hard),minimum_base_height_m=minimum_height,
        report_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest()))
exits=sum(r['exited'] for r in rows)
findings=sum(r['hard_findings'] for r in rows)
stops=sum(bool(r['reason']) for r in rows)
result=dict(episodes=len(rows),exits=exits,actual_limit_findings=findings,checker_stops=stops,
    primary_gate_passed=exits>=90 and findings==0 and stops==0,
    controller_sha256=source_digest,all_frozen_files_match=True,all_randomization_draws_match=True,
    all_independent_exit_scores_match=True,rows=rows)
output=ROOT/'reports/final-audit.json'
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
