"""Offline feasibility audit of delay identification from free-space arm residuals.

Delivered targets are shifted back to recover issued targets for this historical
trace analysis only. Actual delay labels and simulator orientation never enter
the controller. New on-policy calibration must use its own issued-command log.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.kinematics import ArmModel


def inspect(folder):
    report=json.loads((folder/'report.json').read_text())
    delay=report['nominal_command_latency_ms']//20
    with np.load(folder/'trace.npz') as z:
        q,dq=z['q'],z['dq']
        # The interval is fixed before touch navigation starts; no truth contact
        # labels are used to select frames. +2 s accounts for startup handoff.
        indices=np.flatnonzero((z['time']>=5.5)&(z['time']<7.))
        targets,torques=z['joint_targets'],z['feedforward']
        quats=z['qpos'][:,3:7]
        model=ArmModel()
        values=[[],[],[]]
        for index in indices:
            kin=model.evaluate(q[index],quats[max(index-1,0)])
            gravity=np.r_[kin['left']['gravity'],kin['right']['gravity']]
            for age in range(3):
                j=index-1-age+delay
                residual=gravity-(60*(targets[j,15:]-q[index,15:])-1.5*dq[index,15:]+torques[j,15:])
                values[age].append(residual)
        scores=[float(np.mean(np.asarray(v)**2)) for v in values]
        return dict(case=folder.name,actual_delay=delay,scores=scores,selected=int(np.argmin(scores)),
            residual_variance=[float(np.var(v,axis=0).sum()) for v in values])


if __name__=='__main__':
    rows=[inspect(p.parent) for p in sorted((ROOT/'evidence/stability/yaw-ablation-20261110').glob('c0-*/report.json'))]
    print(json.dumps(rows,indent=2))
