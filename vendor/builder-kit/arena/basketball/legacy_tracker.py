"""Reviewed legacy basketball tracking; retained for older controller versions."""
import numpy as np
from .policy import BALL_R

class DribbleTracker:
    """Ball-only bookkeeping of the dribble phase (runs on the robot next to the ball tracker)."""

    def __init__(self, dt, first_hand):
        self.dt = dt
        self.next_hand = int(first_hand)  # 0 left, 1 right
        self.expect = 1  # 1: ball released, waiting for a bounce between the feet; 0: waiting for the hand
        self.since_bounce = 0.0
        self.airborne = True
        self.crossings = 0
        self.bounces = 0
        self.bad_bounces = 0

    def update(self, ball_pos_w, ball_vel_w, feet_w, hand_contact, body_left_w):
        """ball/feet in world frame; hand_contact = (left, right) physical hand-ball contact flags
        (simulator contacts here; on hardware a ball-velocity discontinuity at the hand);
        body_left_w = robot's +y axis in world (xy)."""
        on_floor = ball_pos_w[2] < BALL_R + 0.02
        bounce = on_floor and self.airborne
        self.airborne = not on_floor
        self.since_bounce = 0.0 if bounce else self.since_bounce + self.dt
        touched = None
        for h in (0, 1):
            if hand_contact[h]:
                touched = h
        gate = 0.5 * (feet_w[0][:2] + feet_w[1][:2])
        u = feet_w[0][:2] - feet_w[1][:2]
        half = 0.5 * np.linalg.norm(u) + 1e-6
        u = u / (2 * half)
        n_left = np.array([-u[1], u[0]])
        n_left *= np.sign(np.dot(n_left, body_left_w[:2]) + 1e-9)
        crossing = False
        if bounce:
            self.bounces += 1
            along = np.dot(ball_pos_w[:2] - gate, u)
            perp = np.dot(ball_pos_w[:2] - gate, n_left)
            in_gate = abs(along) < 0.8 * half and abs(perp) < 0.15
            want = 1.0 if self.next_hand == 1 else -1.0
            dir_ok = want * np.dot(ball_vel_w[:2], n_left) > 0.05
            if self.expect == 1 and in_gate and dir_ok:
                crossing = True
                self.crossings += 1
                self.next_hand = 1 - self.next_hand
                self.expect = 0
            elif self.expect == 1:
                self.bad_bounces += 1
                self.expect = 0
        if touched is not None:
            if touched != self.next_hand:
                self.next_hand = touched
            self.expect = 1
        return crossing

    def cue(self, stance):
        return np.array([1.0 if self.next_hand == 1 else -1.0, 1.0 if self.expect == 1 else -1.0,
                         min(self.since_bounce, 1.0), 1.0 if stance == 0 else -1.0], dtype=np.float32)
