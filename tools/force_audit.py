import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import sys
import json
import numpy as np
import mujoco
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.kit import Plant
path = ROOT/sys.argv[1]
report = json.loads((path/'report.json').read_text())
p = Plant(scene=report['scene'])
with np.load(path/'trace.npz') as z:
    norms = np.linalg.norm(z['true_force'],axis=-1).max(axis=1)
    for i in np.argsort(norms)[-8:][::-1]:
        p.data.qpos[:] = z['qpos'][i]
        mujoco.mj_forward(p.model,p.data)
        contacts = []
        for c in p.data.contact:
            names = [p.model.geom(int(g)).name for g in c.geom]
            if any(name and 'touch_hand' in name for name in names):
                bodies = [p.model.body(int(p.model.geom_bodyid[int(g)])).name for g in c.geom]
                contacts.append((names,bodies,round(c.dist,5)))
        print(round(z['time'][i],2),z['state'][i],round(norms[i],2),z['true_force'][i].round(1).tolist(),contacts)
