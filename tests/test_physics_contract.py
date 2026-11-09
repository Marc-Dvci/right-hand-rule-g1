from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import mujoco

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.kit import KIT, Plant
from policy.kinematics import ArmModel


def test_vendored_kit_matches_every_upstream_fingerprint():
    manifest = json.loads((KIT/'UPSTREAM_FILES.json').read_text())
    for row in manifest['files']:
        assert hashlib.sha256((KIT/row['path']).read_bytes()).hexdigest() == row['sha256'], row['path']


def test_arm_fk_jacobian_and_gravity_match_mujoco():
    p = Plant(scene=ROOT/'scene/flat.xml')
    model = ArmModel()
    rng = np.random.default_rng(731)
    for _ in range(30):
        p.data.qpos[p.qadr] = rng.uniform(-.35, .35, 29)
        quat = np.r_[1., rng.normal(0, .05, 3)]
        quat /= np.linalg.norm(quat)
        p.data.qpos[3:7] = quat
        p.data.qvel[:] = 0
        mujoco.mj_forward(p.model, p.data)
        kin = model.evaluate(p.q(), quat)
        for side, first in (('left',15), ('right',22)):
            body = p.model.body(side+'_wrist_yaw_link').id
            hand = p.data.xpos[body]+p.data.xmat[body].reshape(3,3)@[.075,0,0]
            np.testing.assert_allclose(kin[side]['position']+p.data.qpos[:3], hand, atol=1e-10)
            jacp, jacr = np.zeros((3,p.model.nv)), np.zeros((3,p.model.nv))
            mujoco.mj_jac(p.model,p.data,jacp,jacr,hand,body)
            np.testing.assert_allclose(kin[side]['jacobian'], jacp[:,p.vadr[first:first+7]], atol=1e-10)
            np.testing.assert_allclose(kin[side]['gravity'], p.data.qfrc_bias[p.vadr[first:first+7]], atol=1e-8)


def test_scene_keeps_free_base_robot_contract():
    p = Plant(scene=ROOT/'scene/flat.xml')
    assert p.model.nu == 29
    assert p.model.joint('floating_base_joint').type == mujoco.mjtJoint.mjJNT_FREE
    assert p.floor >= 0
    assert not p.fallen()
