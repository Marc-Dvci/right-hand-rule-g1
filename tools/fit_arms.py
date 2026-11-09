import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import least_squares
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.kinematics import ArmModel
from policy.networks import DEFAULT

model = ArmModel()
q = DEFAULT.astype(float).copy()
for side, first, goal, seed, lo, hi in [
    ('right', 22, [.12, -.40, .16], [0, -1.3, 0, .8], [-2, -2.2, -2., -.8], [1.5, .1, 2., 1.8]),
    ('left', 15, [.40, .14, .16], [-1.3, .1, 0, .25], [-2.5, -.8, -2, -.8], [1, 1.5, 2, 1.8])]:
    def residual(x):
        q[first:first+4] = x
        hand = model.evaluate(q, [1, 0, 0, 0])[side]
        return np.r_[20*(hand['position']-goal), .03*(x-seed)]
    fit = least_squares(residual, seed, bounds=(lo, hi))
    q[first:first+4] = fit.x
    hand = model.evaluate(q, [1, 0, 0, 0])[side]
    print(side, q[first:first+7].round(4).tolist(), 'hand', hand['position'].round(4).tolist(), 'gravity', hand['gravity'].round(3).tolist())
(ROOT/'policy/models/arm_pose.json').write_text(json.dumps(q[15:].tolist(), indent=2)+'\n')
