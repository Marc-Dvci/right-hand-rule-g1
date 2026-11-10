"""Replay all successful development sensor streams under the targeted recovery.

This is command-stream nonregression, not a newly randomized physics run. No
simulator/base/contact/layout data enters the replayed controller.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.controller import Controller
from container.timing import TimedPolicy
from tools.sensor_replay import policy_digest,digest


def check_episode(path):
    r=json.loads(path.read_text())
    control=dict(r['control_parameters'],arc_reacquire=True)
    controller=Controller(r['mode'],parameters=r['controller_parameters'],control=control)
    timing=TimedPolicy(controller,**r['transport_config'])
    with np.load(path.parent/'trace.npz',allow_pickle=False) as archive:
        fields=('q','dq','observation_quat','observation_gyro','observation_time','issued_targets','issued_feedforward')
        data={name:archive[name] for name in fields}
        ready=archive['host_ready'] if 'host_ready' in archive else data['observation_time']>r['policy_handoff_at_secs']
    maximum=0.
    first_difference=None
    for i in range(len(data['q'])):
        obs=dict(q=data['q'][i],dq=data['dq'][i],quat=data['observation_quat'][i],gyro=data['observation_gyro'][i])
        command=timing.act(obs,i+1,bool(ready[i]))
        error=max(float(np.max(abs(command['q']-data['issued_targets'][i]))),
                  float(np.max(abs(command['tau']-data['issued_feedforward'][i]))))
        maximum=max(maximum,error)
        if error and first_difference is None:
            first_difference=i
    return dict(layout=r['layout_id'],seed=r['seed'],calls=len(data['q']),exact_match=maximum==0.,
        maximum_difference=maximum,first_difference=first_difference,baseline_controller_sha256=r['controller_sha256'],
        original_report_sha256=digest(path),original_trace_sha256=digest(path.parent/'trace.npz'),
        simulator_imported=any(name=='mujoco' or name.startswith('mujoco.') for name in sys.modules))


if __name__=='__main__':
    folder=ROOT/'evidence/catalog/baseline05-all-development-delay40-20261110'
    paths=[p for p in sorted(folder.glob('*/report.json')) if json.loads(p.read_text())['exited']]
    if len(paths)!=71:
        raise ValueError('Expected every successful episode in the complete baseline cohort')
    rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(check_episode,path) for path in paths]):
            row=future.result()
            rows.append(row)
            print(json.dumps({k:row[k] for k in ('layout','calls','exact_match','maximum_difference')}),flush=True)
    target=ROOT/'review/results/reacquisition-nonregression.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(episodes=len(rows),exact_matches=sum(r['exact_match'] for r in rows),
        candidate_controller_sha256=policy_digest(),scope='Sensor-stream command nonregression only; development data.',
        all_simulator_free=not any(r['simulator_imported'] for r in rows),rows=rows),indent=2)+'\n')
    raise SystemExit(0 if all(r['exact_match'] for r in rows) else 2)
