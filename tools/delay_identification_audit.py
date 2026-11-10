"""Offline ARX feasibility check. Delay labels recover historical issued logs only."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]


def inspect(folder):
    r=json.loads((folder/'report.json').read_text())
    actual=r['nominal_command_latency_ms']//20
    with np.load(folder/'trace.npz') as z:
        q,dq=z['q'],z['dq']
        indices=np.flatnonzero((z['time']>=3.)&(z['time']<6.8))
        target=z['joint_targets']
        ff=z['feedforward']
        scores=[]
        for delay in range(3):
            joint_scores=[]
            for joint in (15,16,18,22,23,25):
                i=indices
                j=i-delay+actual
                qbar=(q[i,joint]+q[i+1,joint])/2
                vbar=(dq[i,joint]+dq[i+1,joint])/2
                u=60*target[j,joint]+ff[j,joint]
                torque=u-60*qbar-1.5*vbar
                X=np.column_stack([torque,vbar,np.ones(len(i)),qbar])
                y=(dq[i+1,joint]-dq[i,joint])/.02
                fit=np.linalg.lstsq(X,y,rcond=None)[0]
                error=np.mean((X@fit-y)**2)
                if fit[0]<=0:
                    error+=1e4
                joint_scores.append(error)
            scores.append(float(np.mean(joint_scores)))
    return dict(case=folder.name,actual=actual,scores=scores,selected=int(np.argmin(scores)))


if __name__=='__main__':
    print(json.dumps([inspect(p.parent) for p in sorted((ROOT/'evidence/stability/yaw-ablation-20261110').glob('c0-*/report.json'))],indent=2))
