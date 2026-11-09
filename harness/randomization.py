"""Declared simulator perturbations; nothing in this module enters the policy."""
import numpy as np
import mujoco


def parameters(seed):
    rng = np.random.default_rng(seed ^ 0x54AC71)
    return dict(corridor_width=float(rng.uniform(1.1,1.4)),wall_friction=float(rng.uniform(.2,.6)),
        hand_friction=float(rng.uniform(.12,.35)),floor_friction=float(rng.uniform(.6,1.2)),
        link_mass_scale=float(rng.uniform(.9,1.1)),motor_strength=float(rng.uniform(.9,1.1)),
        joint_friction_scale=float(rng.uniform(.8,1.2)),encoder_std_rad=float(rng.uniform(.0002,.001)),
        gyro_std_rad_s=float(rng.uniform(.002,.01)),imu_rotation_std_rad=float(rng.uniform(.0002,.002)),
        imu_yaw_drift_rad_s=float(rng.uniform(-.0005,.0005)),command_latency_steps=int(rng.integers(0,3)),
        start_xy_m=rng.uniform(-.04,.04,2).tolist(),start_yaw_rad=float(rng.uniform(-.06,.06)))


def apply(plant, params):
    m,d = plant.model,plant.data
    for g in range(m.ngeom):
        name = m.geom(g).name or ''
        if name.startswith('wall_'):
            m.geom_friction[g,0] = params['wall_friction']
        elif 'touch_hand' in name:
            m.geom_friction[g,0] = params['hand_friction']
        elif name == 'safety_floor' or m.geom_priority[g] == 1:
            # Foot geoms have priority 1 in the kit, overriding the plane.
            # Randomize both so this is the effective friction, not a label.
            m.geom_friction[g,0] = params['floor_friction']
    robot_bodies = sorted({int(m.geom_bodyid[g]) for g in plant.robot_geoms})
    m.body_mass[robot_bodies] *= params['link_mass_scale']
    m.body_inertia[robot_bodies] *= params['link_mass_scale']
    m.dof_frictionloss[plant.vadr] *= params['joint_friction_scale']
    m.jnt_actfrcrange[plant.joints] *= params['motor_strength']
    qpos,qvel = d.qpos.copy(),d.qvel.copy()
    mujoco.mj_setConst(m,d)
    d.qpos[:],d.qvel[:] = qpos,qvel
    d.qpos[:2] += params['start_xy_m']
    a = params['start_yaw_rad']/2
    d.qpos[3:7] = SensorNoise.multiply([np.cos(a),0,0,np.sin(a)],d.qpos[3:7].copy())
    mujoco.mj_forward(m,d)


class SensorNoise:
    def __init__(self,seed,params):
        self.rng = np.random.default_rng(seed ^ 0xB1703)
        self.params = params

    @staticmethod
    def multiply(a,b):
        w,x,y,z = a
        v,p,q,r = b
        return np.array([w*v-x*p-y*q-z*r,w*p+x*v+y*r-z*q,w*q-x*r+y*v+z*p,w*r+x*q-y*p+z*v])

    def observe(self,obs,t):
        p,rng = self.params,self.rng
        out = dict(q=np.array(obs['q'])+rng.normal(0,p['encoder_std_rad'],29),
                   dq=np.array(obs['dq'])+rng.normal(0,p['encoder_std_rad']*5,29),
                   gyro=np.array(obs['gyro'])+rng.normal(0,p['gyro_std_rad_s'],3))
        a = rng.normal(0,p['imu_rotation_std_rad'],3)
        a[2] += p['imu_yaw_drift_rad_s']*t
        noise = np.r_[1.,a/2]
        noise /= np.linalg.norm(noise)
        out['quat'] = self.multiply(noise,np.array(obs['quat']))
        return out
