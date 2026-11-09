import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.kinematics import ArmModel
from policy.networks import rotation
from policy.controller import wrap
path = ROOT/sys.argv[1]
r = json.loads((path/'report.json').read_text())
walls = json.loads(Path(r['scene']).with_suffix('.json').read_text())['walls']
model = ArmModel()
points, errors = [], []
with np.load(path/'trace.npz') as z:
    for i in range(0,len(z['time']),5):
        if z['state'][i] != 'FOLLOW':
            points = []
            continue
        if z['estimated_force'][i,1,1] < 4:
            continue
        quat = z['qpos'][i,3:7]
        hand = model.evaluate(z['q'][i],quat)['right']['position']
        points.append((z['time'][i],z['odometry'][i,:2]+hand[:2]))
        points = [p for p in points if z['time'][i]-p[0] < 3.5]
        if len(points) < 12 or np.linalg.norm(points[-1][1]-points[0][1]) < .25:
            continue
        pts = np.array([p[1] for p in points])
        _,_,vh = np.linalg.svd(pts-pts.mean(axis=0), full_matrices=False)
        candidate = np.arctan2(vh[0,1],vh[0,0])
        actual_hand = z['qpos'][i,:2]+hand[:2]
        nearest, distance = None, 1e9
        for a,b in walls:
            a,b = np.array(a),np.array(b)
            v = b-a
            p = a+np.clip((actual_hand-a)@v/(v@v),0,1)*v
            d = np.linalg.norm(actual_hand-p)
            if d < distance:
                distance,nearest = d,np.arctan2(v[1],v[0])
        if distance < .1:
            errors.append(min(abs(wrap(candidate-nearest)),abs(wrap(candidate-nearest-np.pi))))
print('samples',len(errors),'median deg',np.degrees(np.median(errors)) if errors else None,
      '90th deg',np.degrees(np.quantile(errors,.9)) if errors else None)
