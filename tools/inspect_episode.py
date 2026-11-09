import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ.setdefault('MUJOCO_GL', 'egl')
import argparse
from pathlib import Path
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.networks import rotation

p = argparse.ArgumentParser()
p.add_argument('directory', type=Path)
p.add_argument('--frame', type=float)
args = p.parse_args()
path = args.directory if args.directory.is_absolute() else ROOT/args.directory
with np.load(path/'trace.npz') as z:
    if args.frame is None:
        for i in range(0, min(len(z['time']), 2000), 100):
            print(f'{z["time"][i]:.1f} {z["state"][i]:14} pos {z["qpos"][i, :2].round(2)}',
                  'est', z['estimated_force'][i].round(1).tolist(), 'true', z['true_force'][i].round(1).tolist(),
                  'vel', z['velocity'][i, :2].round(2), 'cmd', z['command'][i].round(2))
    else:
        import mujoco
        from PIL import Image
        from harness.kit import Plant
        import json
        report = json.loads((path/'report.json').read_text())
        plant = Plant(scene=report['scene'])
        i = int(np.argmin(abs(z['time']-args.frame)))
        plant.data.qpos[:] = z['qpos'][i]
        mujoco.mj_forward(plant.model, plant.data)
        renderer = mujoco.Renderer(plant.model, height=720, width=1280)
        camera = mujoco.MjvCamera()
        camera.lookat[:] = plant.data.qpos[:3]
        camera.distance = 3.3
        camera.azimuth = -65
        camera.elevation = -35
        renderer.update_scene(plant.data, camera=camera)
        Image.fromarray(renderer.render()).save(path/'frame.png')
        renderer.close()
