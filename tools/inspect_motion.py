import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.networks import rotation
from policy.kinematics import ArmModel

for name in sys.argv[1:] or ['dev-003']:
    with np.load(ROOT/'evidence/walker'/name/'trace.npz') as z:
        qpos = z['qpos']
        for i in range(0, len(qpos), 500):
            R = rotation(qpos[i, 3:7])
            print(name, round(i*.02, 1), 'yaw', round(np.arctan2(R[1, 0], R[0, 0]), 3), 'cmd', z['commands'][i].round(3))
        kin = ArmModel()
        state = qpos[min(1000, len(qpos)-1)]
        for side, spec in kin.evaluate(state[7:], state[3:7]).items():
            print(side, {k: v.round(3).tolist() for k, v in spec.items()})
