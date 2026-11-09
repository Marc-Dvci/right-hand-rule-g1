import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.kinematics import ArmModel
from policy.networks import DEFAULT
model = ArmModel()
q = DEFAULT.astype(float).copy()
q[15:] = json.loads((ROOT/'policy/models/arm_pose.json').read_text())
for side in ('left','right'):
    J = model.evaluate(q,[1,0,0,0])[side]['jacobian']
    print('Reference',side,'singular values (first 4 joints):',np.linalg.svd(J[:,:4],compute_uv=False))
if len(sys.argv)>1:
    path = ROOT/sys.argv[1]
    with np.load(path/'trace.npz') as z:
        force = np.linalg.norm(z['true_force'],axis=-1)
        i,n = np.unravel_index(force.argmax(),force.shape)
        side = ('left','right')[n]
        kin = model.evaluate(z['q'][i],z['qpos'][i,3:7])
        J = kin[side]['jacobian'][:,:4]
        print('Peak',z['time'][i],side,force[i,n], 'joint angles',z['q'][i,15+7*n:22+7*n])
        print('Singular values',np.linalg.svd(J,compute_uv=False),'force',z['true_force'][i,n])
