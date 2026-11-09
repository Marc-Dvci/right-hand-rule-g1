"""Exact G1 kinematics exported offline; vectorized gravity, NumPy runtime."""
import json
from pathlib import Path
import numpy as np
from .networks import rotation

FOOT_POINTS = np.array([[-.05,.025,-.05],[-.05,-.025,-.05],[.12,.03,-.05],[.12,-.03,-.05]])


def axis_rotation(axis, angle):
    a = np.asarray(axis)
    x, y, z = a
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + np.sin(angle)*skew + (1-np.cos(angle))*(skew@skew)


class ArmModel:
    def __init__(self):
        rows = json.loads((Path(__file__).parent/'models/kinematics.json').read_text())
        self.rows = rows
        self.names = {r['name']: i for i,r in enumerate(rows)}
        self.parents = [self.names.get(r['parent'], -1) for r in rows]
        self.rest = np.array([rotation(r['quat']) for r in rows])
        self.offsets = np.array([r['pos'] for r in rows])
        self.inertial_offsets = np.array([r['ipos'] for r in rows])
        self.axes = np.array([r['axis'] for r in rows])
        self.skews, self.square_skews = [], []
        self.descendant_mass = np.zeros((29,len(rows)))
        chains = []
        for b, row in enumerate(rows):
            parent = self.parents[b]
            chain = chains[parent].copy() if parent >= 0 else []
            if row['motor'] >= 0:
                chain.append(row['motor'])
            chains.append(chain)
            for motor in chain:
                self.descendant_mass[motor,b] = row['mass']
            x,y,z = row['axis']
            skew = np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
            self.skews.append(skew)
            self.square_skews.append(skew@skew)
        self.mass_sum = self.descendant_mass.sum(axis=1)

    def evaluate(self, q, quat):
        n = len(self.rows)
        positions, rotations = np.zeros((n,3)), np.zeros((n,3,3))
        origins, axes = np.zeros((29,3)), np.zeros((29,3))
        for b,row in enumerate(self.rows):
            parent, motor = self.parents[b], row['motor']
            if parent < 0:
                rotations[b] = rotation(quat)
                continue
            Rp = rotations[parent]
            positions[b] = positions[parent]+Rp@self.offsets[b]
            R = Rp@self.rest[b]
            if motor >= 0:
                origins[motor] = positions[b]
                axes[motor] = R@self.axes[b]
                angle = q[motor]
                R = R@(np.eye(3)+np.sin(angle)*self.skews[b]+(1-np.cos(angle))*self.square_skews[b])
            rotations[b] = R
        centers = positions + np.einsum('bij,bj->bi',rotations,self.inertial_offsets)
        moments = self.descendant_mass@centers-self.mass_sum[:,None]*origins
        gravity = 9.81*(axes[:,0]*moments[:,1]-axes[:,1]*moments[:,0])
        out = {}
        for side, first in (('left', 15), ('right', 22)):
            b = self.names[side+'_wrist_yaw_link']
            hand = positions[b]+rotations[b]@[.075,0,0]
            J = np.cross(axes[first:first+7],hand-origins[first:first+7]).T
            out[side] = dict(position=hand, jacobian=J, gravity=gravity[first:first+7])
        foot_ids = [self.names[s+'_ankle_roll_link'] for s in ('left','right')]
        out['feet'] = positions[foot_ids]
        out['foot_rotations'] = rotations[foot_ids]
        return out
