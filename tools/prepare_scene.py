"""Build a self-contained scene and export exact upper-body kinematics."""
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.kit import Plant, KIT
import mujoco
import numpy as np


def main():
    source = KIT / 'packages/policy_safety/src/policy_safety/robots/g1'
    target = ROOT / 'scene/robot'
    if not target.exists():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    xml = ET.parse(target / 'g1_robot.xml')
    xml.find('compiler').set('meshdir', '.')
    for mesh in xml.findall('.//mesh'):
        mesh.set('file', 'third_party/unitree_g1/assets/' + mesh.get('file'))
    for side in ('left', 'right'):
        body = xml.find(f'.//body[@name="{side}_wrist_yaw_link"]')
        for palm in body.findall('geom[@class="palm"]'):
            palm.set('contype', '0')
            palm.set('conaffinity', '0')
        ET.SubElement(body, 'geom', name=f'{side}_touch_hand', type='capsule',
                      **{'fromto': '0.025 0 0 0.095 0 0', 'size': '0.025', 'mass': '0',
                         'friction': '0.2 0.005 0.0001', 'rgba': '.05 .75 .7 1', 'condim': '3', 'group': '3'})
    head = xml.find('.//body[@name="head_link"]')
    if head is not None:
        ET.SubElement(head, 'geom', name='blindfold', type='box', pos='0.052 0 0.015',
                      size='0.026 0.085 0.035', rgba='0.025 0.035 0.05 1', contype='0', conaffinity='0', mass='0')
    xml.write(target / 'g1_touch.xml', encoding='unicode')
    scene = ROOT / 'scene/flat.xml'
    scene.write_text('''<mujoco model="right_hand_rule">
  <include file="robot/g1_touch.xml"/>
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <visual><global offwidth="1280" offheight="720"/><quality shadowsize="2048"/></visual>
  <asset><texture name="floor_tex" type="2d" builtin="checker" width="512" height="512" rgb1=".12 .16 .20" rgb2=".14 .18 .22"/>
  <material name="floor_mat" texture="floor_tex" texrepeat="1 1" reflectance=".1"/></asset>
  <worldbody><geom name="safety_floor" type="plane" size="0 0 .05" friction="1.15" material="floor_mat"/>
  <light pos="0 -3 5" dir="0 .3 -1" diffuse=".8 .85 .9"/></worldbody>
</mujoco>''')
    plant = Plant(scene=scene)
    m = plant.model
    rows = []
    for b in range(1, m.nbody):
        name = m.body(b).name
        joint_ids = list(range(m.body_jntadr[b], m.body_jntadr[b]+m.body_jntnum[b]))
        motor = -1
        axis = [0, 0, 1]
        for j in joint_ids:
            if j in plant.joints:
                motor = int(np.flatnonzero(plant.joints == j)[0])
                axis = m.jnt_axis[j].tolist()
                assert np.linalg.norm(m.jnt_pos[j]) < 1e-8
        rows.append(dict(name=name, parent=m.body(int(m.body_parentid[b])).name,
                         pos=m.body_pos[b].tolist(), quat=m.body_quat[b].tolist(),
                         ipos=m.body_ipos[b].tolist(), mass=float(m.body_mass[b]), motor=motor, axis=axis))
    (ROOT / 'policy/models/kinematics.json').write_text(json.dumps(rows, indent=2)+'\n')
    print('Scene prepared:', scene, 'kinematic links:', len(rows))


if __name__ == '__main__':
    main()
