import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import sys
import json
import numpy as np
import mujoco
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.kit import Plant
from policy.kinematics import ArmModel
from policy.networks import rotation
directory = ROOT/(sys.argv[1] if len(sys.argv)>1 else 'evidence/development/wall-001')
r = json.loads((directory/'report.json').read_text())
p = Plant(scene=r['scene'])
kin = ArmModel()
with np.load(directory/'trace.npz') as z:
    print('Truth max', abs(z['true_force']).max(axis=0))
    for sec in (0, 6, 8, 10, 12, 14, 20):
        i = np.argmin(abs(z['time']-sec))
        p.data.qpos[:] = z['qpos'][i]
        mujoco.mj_forward(p.model, p.data)
        q = p.q()
        R = rotation(p.data.qpos[3:7])
        print('t', sec, 'yaw', np.arctan2(R[1,0], R[0,0]), 'waist', q[12:15].round(2), 'arm', q[22:].round(2))
        k = kin.evaluate(q, p.data.qpos[3:7])
        for side in ('right', 'left'):
            b = p.model.body(side+'_wrist_yaw_link').id
            actual = p.data.xpos[b]+p.data.xmat[b].reshape(3,3)@[.075,0,0]
            predicted = p.data.qpos[:3]+k[side]['position']
            print(side, 'mj', actual.round(3), 'fk error', np.linalg.norm(predicted-actual))
        print('contacts', [(p.model.geom(int(c.geom[0])).name, p.model.geom(int(c.geom[1])).name, round(c.dist,4)) for c in p.data.contact if 'wall' in str(p.model.geom(int(c.geom[0])).name)+str(p.model.geom(int(c.geom[1])).name)])
