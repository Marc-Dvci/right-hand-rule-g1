"""Leg kinematic odometry; it never consumes simulator base velocity/position."""
import numpy as np
from .networks import rotation
from .kinematics import FOOT_POINTS


class Odometry:
    def __init__(self):
        self.previous = None
        self.previous_rotations = None
        self.velocity = np.zeros(3)
        self.position = np.zeros(3)
        self.distance = 0.

    def update(self, feet, quat, dt=.02, foot_rotations=None):
        if foot_rotations is None:
            foot_rotations = np.array([np.eye(3),np.eye(3)])
        points = feet[:,None,:]+np.einsum('bij,kj->bki',foot_rotations,FOOT_POINTS)
        lowest = np.argmin(points[:,:,2],axis=1)
        if self.previous is not None:
            current = points[np.arange(2),lowest]
            old = self.previous+np.einsum('bij,bj->bi',self.previous_rotations,FOOT_POINTS[lowest])
            velocities = -(current-old)/dt
            heights = current[:,2]
            low = np.min(heights)
            weights = np.exp(-np.clip((heights-low)/.003, 0, 50))
            v = np.average(velocities, axis=0, weights=weights)
            v = np.clip(v, -1.5, 1.5)
            self.velocity += (1-np.exp(-dt/.12))*(v-self.velocity)
            self.position += self.velocity*dt
            self.distance += np.linalg.norm(self.velocity[:2])*dt
        self.previous = feet.copy()
        self.previous_rotations = foot_rotations.copy()
        return rotation(quat).T @ self.velocity
