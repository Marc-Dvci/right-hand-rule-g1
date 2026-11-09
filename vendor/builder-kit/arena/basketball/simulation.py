"""Reviewed basketball simulation interface; no submitted Python is imported."""
import json
import os
from pathlib import Path
import mujoco
import numpy as np
from .policy import BALL_R, DribbleTracker
HERE = ""
SCENE = ""

def yaw_matrix(q):
    w, x, y, z = q
    yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])

class Sim:
    def __init__(self, args, tracker_class=DribbleTracker):
        self.tracker_class = tracker_class
        self.m = mujoco.MjModel.from_xml_path(SCENE)
        self.m.opt.timestep = args.timestep
        if args.solver_iterations:
            self.m.opt.iterations = args.solver_iterations
            self.m.opt.ls_iterations = 50
        self.d = mujoco.MjData(self.m)
        self.ctrl_dt = 0.02
        self.n_sub = int(round(self.ctrl_dt / self.m.opt.timestep))
        self.args = args
        m = self.m
        self.keys = {0: m.key("stance_left_front"), 1: m.key("stance_right_front")}
        self.sid = {n: m.site(n).id for n in ("imu_in_pelvis", "left_palm", "right_palm", "left_foot", "right_foot")}
        self.hand_geoms = [m.geom("left_hand_collision").id, m.geom("right_hand_collision").id]
        self.leg_geoms = [m.geom(f"{s}_{g}").id for s in ("left", "right") for g in
                          ("thigh_collision", "shin_collision", "linkage_brace_collision", "hip_collision", "foot")]
        self.trunk_geoms = [m.geom(g).id for g in ("pelvis_collision", "torso_collision", "head_collision")]
        self.ball_geom = m.geom("ball").id
        self.floor_geom = m.geom("floor").id
        self.foot_geoms = [m.geom("left_foot").id, m.geom("right_foot").id]

    def sensor(self, n):
        return self.d.sensor(n).data.copy()

    def randomize(self, rng):
        """Same physics randomisation as training (dribble_env.domain_randomize), applied to the C model."""
        m = self.m
        calib = json.load(open(os.path.join(HERE, "assets", "ball_calibration.json")))
        d_lo, d_hi = sorted(calib["dampratio_legal_range"])
        base = mujoco.MjModel.from_xml_path(SCENE)
        for p in range(m.npair):
            n = m.pair(p).name
            if n in ("floor_left_foot", "floor_right_foot"):
                m.pair_friction[p, :2] = rng.uniform(0.4, 1.0)
            elif n == "floor_ball":
                m.pair_friction[p, :2] = rng.uniform(0.4, 0.9)
            elif n.startswith("ball_"):
                m.pair_friction[p, :2] = rng.uniform(0.5, 1.0)
            if "ball" in n:
                m.pair_solref[p, 1] = rng.uniform(d_lo, d_hi)
        m.body_mass[:] = base.body_mass * rng.uniform(0.9, 1.1, size=m.nbody)
        m.body_mass[m.body("torso_link").id] += rng.uniform(-1, 1)
        bm = rng.uniform(21.5, 22.5) * 0.028349523
        bid = m.body("ball").id
        m.body_inertia[bid] = base.body_inertia[bid] * bm / base.body_mass[bid]
        m.body_mass[bid] = bm
        m.dof_frictionloss[6:35] = base.dof_frictionloss[6:35] * rng.uniform(0.5, 2.0, size=29)
        m.dof_armature[6:35] = base.dof_armature[6:35] * rng.uniform(1.0, 1.05, size=29)
        g = rng.uniform(0.9, 1.1, size=29)
        m.actuator_gainprm[:, 0] = base.actuator_gainprm[:, 0] * g
        m.actuator_biasprm[:, 1] = base.actuator_biasprm[:, 1] * g
        m.actuator_biasprm[:, 2] = base.actuator_biasprm[:, 2] * rng.uniform(0.9, 1.1, size=29)
        mujoco.mj_setConst(m, self.d)

    def reset(self, rng, stance=None):
        m, d = self.m, self.d
        mujoco.mj_resetData(m, d)
        if stance is None:
            stance = int(rng.integers(0, 2))
        key = self.keys[stance]
        d.qpos[:] = key.qpos
        profile_targets = getattr(self, 'profile_stance_targets', None)
        if profile_targets is not None:
            d.qpos[7:36] = profile_targets[stance] + rng.uniform(-0.005, 0.005, size=29)
        else:
            d.qpos[7:36] += rng.uniform(-0.03, 0.03, size=29)
        yaw = rng.uniform(-np.pi, np.pi)
        q = np.array([np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)])
        r = np.zeros(4)
        mujoco.mju_mulQuat(r, d.qpos[3:7].copy(), q)
        d.qpos[3:7] = r
        d.ctrl[:] = key.ctrl if profile_targets is None else profile_targets[stance]
        mujoco.mj_forward(m, d)
        next_hand = 1 - stance
        palm = d.geom_xpos[self.hand_geoms[next_hand]].copy()  # hand capsule centre
        feet = np.stack([d.site_xpos[self.sid["left_foot"]], d.site_xpos[self.sid["right_foot"]]])
        gate = 0.5 * (feet[0] + feet[1])
        release = rng.uniform() < 0.3
        pelvis = d.site_xpos[self.sid["imu_in_pelvis"]]
        R = yaw_matrix(self.sensor("pelvis_quat"))
        side = -1.0 if next_hand == 1 else 1.0
        if release:
            pos = pelvis + R @ np.array([0.32, 0.30 * side, 0.0])
            pos[2] = 0.38
            pos = pos + rng.uniform(-0.03, 0.03, size=3)
            t_f = rng.uniform(0.15, 0.28)
            h = pos[2] - BALL_R
            v_xy = (gate[:2] - pos[:2]) / t_f
            v_z = min(-(h / t_f - 0.5 * 9.81 * t_f), 0.0)
            vel = np.array([v_xy[0], v_xy[1], v_z])
            expect = 0  # a spawned ball never scores by itself
        else:
            pos = pelvis + R @ np.array([0.22, 0.30 * side, 0.0])
            pos[2] = 0.50
            pos = pos + rng.uniform(-0.04, 0.04, size=3)
            vel = np.zeros(3)
            expect = 0
        d.qpos[36:39] = pos
        d.qpos[39:43] = [1, 0, 0, 0]
        d.qvel[35:38] = vel
        d.qvel[38:41] = 0
        mujoco.mj_forward(m, d)
        self.stance = stance
        self.stance_qpos = key.qpos[7:36].copy()
        self.stance_ctrl = d.ctrl.copy()
        self.tracker = self.tracker_class(self.ctrl_dt, next_hand)
        self.tracker.expect = expect
        self.ball_buf = []
        self.feet_init = feet[:, :2].copy()
        return stance

    def contacts(self):
        d = self.d
        flags = {"hand": [False, False], "leg": False, "trunk": False, "floor": False, "feet": [False, False]}
        for i in range(d.ncon):
            c = d.contact[i]
            g1, g2 = c.geom1, c.geom2
            other = None
            if g1 == self.ball_geom:
                other = g2
            elif g2 == self.ball_geom:
                other = g1
            if other is not None:
                if other in self.hand_geoms:
                    flags["hand"][self.hand_geoms.index(other)] = True
                elif other in self.leg_geoms:
                    flags["leg"] = True
                elif other in self.trunk_geoms:
                    flags["trunk"] = True
                elif other == self.floor_geom:
                    flags["floor"] = True
            for k, fg in enumerate(self.foot_geoms):
                if (g1 == fg and g2 == self.floor_geom) or (g2 == fg and g1 == self.floor_geom):
                    flags["feet"][k] = True
        return flags

    def observe(self, rng):
        """Build the policy observation from IMU, encoders and a (delayed, noisy) ball tracker."""
        d, a = self.d, self.args
        gyro = self.sensor("gyro_pelvis")
        gravity = d.site_xmat[self.sid["imu_in_pelvis"]].reshape(3, 3).T @ np.array([0, 0, -1.0])
        pelvis = d.site_xpos[self.sid["imu_in_pelvis"]].copy()
        pelvis_v = self.sensor("global_linvel_pelvis")
        R = yaw_matrix(self.sensor("pelvis_quat"))
        bp = self.sensor("ball_pos")
        bv = self.sensor("ball_linvel")
        rel = np.concatenate([R.T @ (bp - pelvis), R.T @ (bv - pelvis_v)])
        self.ball_buf.insert(0, rel)
        self.ball_buf = self.ball_buf[:4]
        rel_obs = self.ball_buf[min(a.ball_delay, len(self.ball_buf) - 1)].copy()
        if a.noise:
            gyro = gyro + rng.uniform(-0.2, 0.2, 3)
            gravity = gravity + rng.uniform(-0.05, 0.05, 3)
            rel_obs[:3] += rng.uniform(-0.015, 0.015, 3)
            rel_obs[3:] += rng.uniform(-0.15, 0.15, 3)
        jp_ = d.qpos[7:36].copy()
        jv = d.qvel[6:35].copy()
        if a.noise:
            jp_ = jp_ + rng.uniform(-0.01, 0.01, 29)
            jv = jv + rng.uniform(-1.5, 1.5, 29)
        feet = np.stack([d.site_xpos[self.sid["left_foot"]], d.site_xpos[self.sid["right_foot"]]])
        hand_contact = self.contacts()["hand"]
        crossing = self.tracker.update(bp, bv, feet, hand_contact, R[:, 1])
        return {
            "gyro": gyro, "gravity": gravity, "joint_pos_rel": jp_ - self.stance_qpos, "joint_vel": jv,
            "ball_rel": rel_obs, "cue": self.tracker.cue(self.stance), "stance_targets": self.stance_ctrl,
        }, crossing

    def step(self, targets):
        self.d.ctrl[:] = np.clip(targets, self.m.actuator_ctrlrange[:, 0], self.m.actuator_ctrlrange[:, 1])
        for _ in range(self.n_sub):
            mujoco.mj_step(self.m, self.d)
