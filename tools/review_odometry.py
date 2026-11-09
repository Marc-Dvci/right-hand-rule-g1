"""Offline diagnostic only: compare sphere-contact odometry on saved v1 data."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.odometry import Odometry
from policy.kinematics import ArmModel,FOOT_POINTS
from policy.networks import rotation
from harness.randomization import SensorNoise


class SphereOdometry(Odometry):
    def update(self,feet,quat,dt=.02,foot_rotations=None):
        centers=FOOT_POINTS+[0,0,.02]
        points=feet[:,None,:]+np.einsum('bij,kj->bki',foot_rotations,centers)
        lowest=np.argmin(points[:,:,2],axis=1)
        current=points[np.arange(2),lowest]-[0,0,.02]
        if self.previous is not None:
            # A sphere touches along the WORLD normal, not its rotated local z.
            offsets=centers[lowest]-np.einsum('bji,j->bi',foot_rotations,[0,0,.02])
            old=self.previous+np.einsum('bij,bj->bi',self.previous_rotations,offsets)
            velocities=-(current-old)/dt
            weights=np.exp(-np.clip((current[:,2]-current[:,2].min())/.003,0,50))
            v=np.clip(np.average(velocities,axis=0,weights=weights),-1.5,1.5)
            self.velocity+=(1-np.exp(-dt/.12))*(v-self.velocity)
            self.position+=self.velocity*dt
            self.distance+=np.linalg.norm(self.velocity[:2])*dt
        self.previous=feet.copy()
        self.previous_rotations=foot_rotations.copy()
        return rotation(quat).T@self.velocity


if __name__=='__main__':
    base=ROOT.parent/'RightHandRule/evidence/cohorts/final-nominal-v1'
    model=ArmModel()
    for seed in (26111500,26111551,26111559,26111590):
        folder=base/f'navigate-{seed}'
        report=json.loads((folder/'report.json').read_text())
        old,new=Odometry(),SphereOdometry()
        noise=SensorNoise(seed,report['randomized_parameters'])
        with np.load(folder/'trace.npz') as z:
            z={key:z[key] for key in ('observation_time','time','qpos','q','features','command','state','odometry')}
            errors=[[],[]]
            for i,t in enumerate(z['observation_time']):
                previous=max(0,i-1)
                quat=noise.observe(dict(q=np.zeros(29),dq=np.zeros(29),quat=z['qpos'][previous,3:7],gyro=np.zeros(3)),t)['quat']
                kin=model.evaluate(z['q'][i],quat)
                for n,odom in enumerate((old,new)):
                    odom.update(kin['feet'],quat,foot_rotations=kin['foot_rotations'])
                    errors[n].append(np.linalg.norm(odom.position[:2]-(z['qpos'][previous,:2]-z['qpos'][0,:2])))
            tail=(z['time']>z['time'][-1]-2)
            print(json.dumps(dict(seed=seed,odom_endpoint=[e[-1] for e in errors],odom_rms=[float(np.sqrt(np.mean(np.square(e)))) for e in errors],
                final_state=str(z['state'][-1]),final_yaw_command=float(np.mean(z['command'][tail,2])),
                last_gyro_z_mean=float(np.mean(z['features'][tail,-86+9]/.5)),
                last_gyro_z_abs_mean=float(np.mean(abs(z['features'][tail,-86+9]/.5))),
                actual_last_displacement=(z['qpos'][-1,:2]-z['qpos'][np.flatnonzero(tail)[0],:2]).tolist(),
                estimated_last_displacement=(z['odometry'][-1,:2]-z['odometry'][np.flatnonzero(tail)[0],:2]).tolist())),flush=True)
