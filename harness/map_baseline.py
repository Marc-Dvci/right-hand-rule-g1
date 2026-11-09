"""Privileged-map control: BFS waypoints + joint/IMU dead reckoning, no touch.

This evaluator-only baseline is never imported into the policy or runner image.
It deliberately receives the true static map; robot position feedback is forbidden.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from collections import deque
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.controller import Parameters,wrap
from policy.networks import Walker,rotation
from policy.kinematics import ArmModel
from policy.odometry import Odometry


def route(spec,width,size=3):
    walls=np.asarray(spec['walls'])/width
    def blocked(a,b):
        midpoint=(np.array(a)+b)/2
        for wall in walls:
            lo,hi=wall.min(axis=0),wall.max(axis=0)
            if np.all(midpoint>=lo-1e-6) and np.all(midpoint<=hi+1e-6):
                return True
        return False
    parents={(0,0):None}
    pending=deque([(0,0)])
    goal=(size-1,size-1)
    while pending:
        cell=pending.popleft()
        if cell==goal:
            break
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1)):
            nxt=(cell[0]+dx,cell[1]+dy)
            if min(nxt)<0 or max(nxt)>=size or nxt in parents or blocked(cell,nxt):
                continue
            parents[nxt]=cell
            pending.append(nxt)
    cells=[]
    cell=goal
    while cell is not None:
        cells.append(cell)
        cell=parents[cell]
    points=[np.asarray(c)*width for c in reversed(cells)]
    points.append(np.array([spec['exit']['value']+.2,(size-1)*width]))
    return points[1:]


class MapOnly:
    def __init__(self,points,parameters):
        self.points=points
        self.parameters=Parameters(**parameters)
        self.walker=Walker()
        self.model=ArmModel()
        self.odometry=Odometry()
        self.arm_pose=np.asarray(json.loads((ROOT/'policy/models/arm_pose.json').read_text()))
        self.kp=np.array([150,150,150,200,40,40]*2+[60]*17,float)
        self.kd=np.array([2,2,2,4,2,2]*2+[1.5]*17,float)
        self.age=0.
        self.state='ARMING'
        self.velocity_command=np.zeros(3)
        self.integral=np.zeros(2)
        self.force=self.navigation_force=np.zeros((2,3))
        self.events=[]
        self.initial_arms=None
        self.last_command=None
        self.telemetry={}
        self.index=0

    def act(self,obs,*,ready=True):
        q,dq,quat,gyro=(np.asarray(obs[k]) for k in ('q','dq','quat','gyro'))
        kin=self.model.evaluate(q,quat)
        velocity=self.odometry.update(kin['feet'],quat,foot_rotations=kin['foot_rotations'])
        R=rotation(quat)
        yaw=np.arctan2(R[1,0],R[0,0])
        self.age+=.02*ready
        if self.initial_arms is None:
            self.initial_arms=q[15:].copy()
        cmd=np.zeros(3)
        if self.age>5 and self.index<len(self.points):
            self.state='MAP_WAYPOINT'
            delta=self.points[self.index]-self.odometry.position[:2]
            if np.linalg.norm(delta)<.12:
                self.index+=1
                self.events.append(dict(time=self.age,target='WAYPOINT',index=self.index))
            else:
                error=wrap(np.arctan2(delta[1],delta[0])-yaw)
                cmd[2]=np.clip(2*error,-self.parameters.turn_rate,self.parameters.turn_rate)
                if abs(error)<.25:
                    cmd[0]=min(self.parameters.speed,.6*np.linalg.norm(delta))
                    self.integral=np.clip(self.integral+(cmd[:2]-velocity[:2])*.02,-.25,.25)
                    cmd[:2]=np.clip(cmd[:2]+.9*(cmd[:2]-velocity[:2])+1.8*self.integral,[-.25,-.3],[.4,.3])
                else:
                    self.integral[:]=0
        elif self.age>5:
            self.state='STOP'
        self.velocity_command+=np.clip(cmd-self.velocity_command,[-.003,-.003,-.006],[.003,.003,.006])
        lower=self.walker.update(q,dq,quat,gyro,self.velocity_command)
        alpha=min(1.,self.age/3)
        targets=np.r_[lower,self.initial_arms+alpha*(self.arm_pose-self.initial_arms)]
        tau=np.zeros(29)
        tau[12:15]=np.clip(190*(targets[12:15]-q[12:15])-3.5*dq[12:15],[-25,-20,-20],[25,20,20])
        for side,i in (('left',15),('right',22)):
            tau[i:i+7]=np.clip(alpha*(kin[side]['gravity']-40*(targets[i:i+7]-q[i:i+7])),
                              [-20,-20,-20,-20,-20,-4,-4],[20,20,20,20,20,4,4])
        command=dict(q=targets,dq=np.zeros(29),kp=self.kp.copy(),kd=self.kd.copy(),tau=tau)
        self.last_command=command
        self.telemetry=dict(state=self.state,command=self.velocity_command,velocity=velocity,
                            odometry=self.odometry.position,force=self.force,right_force=0.,front_force=0.)
        return command


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    from harness import evaluate
    from harness.randomization import parameters
    from harness.scenes import make
    width=parameters(a.seed)['corridor_width']
    scene=make('maze',a.seed,width=width)
    spec=json.loads(scene.with_suffix('.json').read_text())
    nav=json.loads((ROOT/'config/navigation.json').read_text())
    points=route(spec,width)
    evaluate.Controller=lambda *args,**kwargs:MapOnly(points,nav)
    report=evaluate.run('maze',a.seed,400,'map_only',None,a.output,parameters=nav,
                        randomize=True,transport=True,transport_config={'max_gap_frames':5},latency_steps=0)
    report['baseline']=dict(name='True map + BFS + joint/IMU dead reckoning, no touch',
                            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            privileged_input='Static scene walls/exit, before episode; no base state feedback',
                            waypoints=[point.tolist() for point in points])
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
