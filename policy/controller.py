"""Touch-only wall following over the attributed NVIDIA locomotion policy."""
import json
from pathlib import Path
import numpy as np
from .networks import Walker, rotation
from .kinematics import ArmModel
from .odometry import Odometry


def wrap(a):
    return (a+np.pi) % (2*np.pi)-np.pi


class Controller:
    """act accepts only q/dq/quat/gyro and host control readiness.

    No maze, contact labels, world coordinates or simulator velocity enter it.
    All distances are estimates from foot kinematics; yaw is from the IMU.
    """
    def __init__(self, mode='navigate', speed=.12):
        if mode not in ('navigate', 'neutral', 'touch_off', 'touch_shuffled', 'walk_test'):
            raise ValueError('Unknown controller mode')
        self.mode = mode
        self.speed = speed
        self.walker = Walker()
        self.model = ArmModel()
        self.arm_pose = np.array(json.loads((Path(__file__).parent/'models/arm_pose.json').read_text()))
        self.kp = np.array([150,150,150,200,40,40]*2 + [60]*17, float)
        self.kd = np.array([2,2,2,4,2,2]*2 + [1.5]*17, float)
        self.reset()

    def reset(self):
        self.walker.reset()
        self.odometry = Odometry()
        self.age = 0.
        self.started = False
        self.state = 'ARMING'
        self.state_age = 0.
        self.state_distance = 0.
        self.state_position = np.zeros(3)
        self.turn_anchor = np.zeros(3)
        self.seek_forward = False
        self.contact_points = []
        self.arc_start = None
        self.heading = None
        self.origin_heading = None
        self.heading_integral = 0.
        self.velocity_integral = np.zeros(2)
        self.velocity_command = np.zeros(3)
        self.navigation_velocity = np.zeros(3)
        self.last_command = None
        self.initial_arms = None
        self.force = np.zeros((2, 3))
        self.navigation_force = np.zeros((2, 3))
        self.bias = np.zeros((2, 3))
        self.force_history = []
        self.lost = 0.
        self.arm_alpha = 0.
        self.right_adjustment = np.zeros(7)
        self.events = []
        self.telemetry = {}

    def transition(self, state):
        self.events.append(dict(time=self.age, source=self.state, target=state,
                                distance=self.odometry.distance))
        self.state, self.state_age = state, 0.
        self.state_distance = self.odometry.distance
        self.state_position = self.odometry.position.copy()
        if state.startswith('RETRACT_'):
            self.turn_anchor = self.odometry.position.copy()
        if state == 'ARC':
            self.contact_points = []
            self.arc_start = self.heading
        self.lost = 0.

    def act(self, observation, *, ready=True):
        q = np.asarray(observation['q'], dtype=float)
        dq = np.asarray(observation['dq'], dtype=float)
        quat = np.asarray(observation['quat'], dtype=float)
        gyro = np.asarray(observation['gyro'], dtype=float)
        if any(a.shape != sh or not np.isfinite(a).all() for a, sh in
               zip((q, dq, quat, gyro), ((29,), (29,), (4,), (3,)))):
            raise ValueError('Invalid joint/IMU observation')
        norm = np.linalg.norm(quat)
        if not .95 <= norm <= 1.05:
            raise ValueError('Invalid IMU quaternion norm')
        quat = quat/norm
        R = rotation(quat)
        yaw = np.arctan2(R[1, 0], R[0, 0])
        kin = self.model.evaluate(q, quat)
        velocity = self.odometry.update(kin['feet'], quat, foot_rotations=kin['foot_rotations'])
        self.navigation_velocity += .045*(velocity-self.navigation_velocity)
        if self.initial_arms is None:
            self.initial_arms = q[15:].copy()
        if not self.started:
            self.heading = yaw
            self.origin_heading = yaw
            if ready:
                self.started = True
        if self.started:
            self.age += .02
            self.state_age += .02
        raw = np.zeros((2, 3))
        if self.last_command is not None:
            for n, (side, i) in enumerate((('left', 15), ('right', 22))):
                motor = self.kp[i:i+7]*(self.last_command['q'][i:i+7]-q[i:i+7]) - self.kd[i:i+7]*dq[i:i+7] + self.last_command['tau'][i:i+7]
                residual = kin[side]['gravity'] - motor
                J = kin[side]['jacobian'][:, :4]
                force_world = np.linalg.solve(J@J.T+np.eye(3)*.0002, J@residual[:4])
                raw[n] = R.T @ force_world
            if 3.5 < self.age < 5.:
                self.bias += .04*(raw-self.bias)
            self.force += .22*(raw-self.bias-self.force)
        self.navigation_force += .065*(self.force-self.navigation_force)
        sensed = self.navigation_force.copy()
        self.force_history.append(sensed)
        if len(self.force_history) > 500:
            self.force_history.pop(0)
        if self.mode == 'touch_off':
            sensed[:] = 0
        elif self.mode == 'touch_shuffled':
            # Fixed long delay destroys the causal alignment without reading truth.
            sensed = self.force_history[max(0, len(self.force_history)-171)]
        front = max(0., -sensed[0, 0])
        right = max(0., sensed[1, 1])
        cmd = np.zeros(3)
        travelled = np.linalg.norm((self.odometry.position-self.state_position)[:2])
        if self.state == 'ARMING' and self.age >= 5.:
            self.transition('FOLLOW' if right > 2.5 else 'FIND')
        if self.mode == 'walk_test' and self.age >= 5.:
            self.state = 'WALK_TEST'
            phase = self.age-5
            if phase < 25:
                cmd[0] = self.speed
            elif phase < 35:
                self.heading += .16*.02
            elif phase < 45:
                self.heading -= .16*.02
            elif phase < 51:
                cmd[1] = -.08
        elif self.state == 'FIND':
            cmd[1] = -.07
            if self.seek_forward:
                cmd[0] = .08
            if right > 3.:
                self.transition('FOLLOW')
                self.seek_forward = False
            elif travelled > 1.5 or self.state_age > 25:
                self.transition('STOP')
        elif self.state == 'FOLLOW':
            cmd[0] = self.speed
            cmd[1] = np.clip(.012*(right-6.), -.07, .07)
            self.lost = self.lost+.02 if right < 3. else max(0., self.lost-.04)
            if front > 5.:
                self.transition('BACKOFF')
            elif self.lost > .6:
                self.transition('ARC')
            if right > 3.5:
                point = self.odometry.position + kin['right']['position']
                self.contact_points.append(point.copy())
                self.contact_points = self.contact_points[-200:]
                if len(self.contact_points) > 35:
                    pts = np.array(self.contact_points)[:, :2]
                    if np.linalg.norm(pts[-1]-pts[0]) > .25:
                        _, _, vh = np.linalg.svd(pts-pts.mean(axis=0), full_matrices=False)
                        tangent = vh[0]
                        candidate = np.arctan2(tangent[1], tangent[0])
                        if abs(wrap(candidate-yaw)) > np.pi/2:
                            candidate = wrap(candidate+np.pi)
                        # Keep this estimate for logging until odometry accuracy
                        # qualifies it for heading feedback.
                        self.wall_heading_estimate = candidate
                        if abs(wrap(candidate-self.heading)) < .5:
                            self.heading = wrap(self.heading+.005*wrap(candidate-self.heading))
        elif self.state == 'ARC':
            cmd[0] = .085
            self.heading = wrap(self.heading-.19*.02)
            if right > 4. and self.state_age > 1.:
                normal = R @ self.navigation_force[1]
                tangent = np.arctan2(normal[1],normal[0])-np.pi/2
                self.heading = wrap(self.origin_heading+np.round((tangent-self.origin_heading)/(np.pi/2))*(np.pi/2))
                self.transition('FOLLOW')
            elif front > 6.:
                cmd[0] = -.035
            elif self.state_age > 35:
                self.transition('STOP')
        elif self.state == 'CLEAR':
            cmd[0] = self.speed
            if front > 5.:
                self.transition('RETRACT_RIGHT')
            elif right > 4.5:
                self.transition('FOLLOW')
            elif travelled > .25:
                self.transition('RETRACT_RIGHT')
        elif self.state == 'BACKOFF':
            cmd[0] = -.06
            if travelled > .12 or self.state_age > 2.5:
                self.transition('RETRACT_LEFT')
        elif self.state.startswith('RETRACT_'):
            if self.state_age > 1.5:
                direction = -1 if self.state.endswith('RIGHT') else 1
                self.seek_forward = direction < 0
                self.heading = wrap(self.heading + direction*np.pi/2)
                self.transition('TURN')
        elif self.state == 'TURN':
            if abs(wrap(self.heading-yaw)) < .075 and abs(gyro[2]) < .15 and self.state_age > 3.:
                self.transition('EXTEND')
            elif self.state_age > 25:
                self.transition('STOP')
        elif self.state == 'EXTEND':
            if self.state_age > 2.:
                self.transition('FIND')
        if self.mode == 'neutral':
            cmd[:] = 0
        if self.state == 'FOLLOW':
            cmd[0] *= max(0., 1-abs(wrap(self.heading-yaw))/.5)
        if self.state.startswith('RETRACT_') or self.state in ('TURN', 'EXTEND'):
            cmd[:2] = np.clip((R.T@(self.turn_anchor-self.odometry.position))[:2]*.8, -.15, .15)
        if self.state not in ('ARMING', 'STOP') and self.mode != 'neutral':
            err = wrap(self.heading-yaw)
            self.heading_integral = np.clip(self.heading_integral+err*.02, -.8, .8)
            cmd[2] = np.clip(2.*err + .5*self.heading_integral, -.24, .24)
            if self.state == 'ARC':
                cmd[2] = -.2
            self.velocity_integral += (cmd[:2]-self.navigation_velocity[:2])*.02
            self.velocity_integral = np.clip(self.velocity_integral, -.25, .25)
            cmd[:2] = np.clip(cmd[:2]+.9*(cmd[:2]-self.navigation_velocity[:2])+1.8*self.velocity_integral, [-.25,-.3], [.4,.3])
        if max(front, right) > 35 and self.state not in ('RETRACT_LEFT', 'RETRACT_RIGHT', 'TURN', 'EXTEND', 'BACKOFF'):
            self.transition('GUARD')
        if self.state in ('ARMING', 'STOP', 'GUARD') or self.mode == 'neutral':
            cmd[:] = 0
            self.velocity_integral *= .95
        self.velocity_command += np.clip(cmd-self.velocity_command, [-.003,-.003,-.006], [.003,.003,.006])
        lower = self.walker.update(q, dq, quat, gyro, self.velocity_command)
        target_alpha = 0. if self.state.startswith('RETRACT_') or self.state in ('TURN', 'GUARD', 'STOP') else min(1., self.age/3.)
        self.arm_alpha += np.clip(target_alpha-self.arm_alpha, -.012, .012)
        targets = np.r_[lower, self.initial_arms+self.arm_alpha*(self.arm_pose-self.initial_arms)]
        if self.state in ('FOLLOW', 'FIND', 'CLEAR') and self.mode not in ('neutral', 'touch_off'):
            J = R.T @ kin['right']['jacobian'][:, :4]
            dy = np.clip(.012*(right-6.)-velocity[1], -.16, .16)*.02
            step = J.T@np.linalg.solve(J@J.T+np.eye(3)*.001, [0, dy, 0])
            self.right_adjustment[:4] = np.clip(self.right_adjustment[:4]+step, -.35, .35)
        else:
            self.right_adjustment *= .96
        targets[22:] += self.arm_alpha*self.right_adjustment
        tau = np.zeros(29)
        tau[12:15] = np.clip(190*(targets[12:15]-q[12:15])-3.5*dq[12:15], [-25,-20,-20], [25,20,20])
        reference = q.copy()
        reference[15:] = targets[15:]
        desired_kinematics = self.model.evaluate(reference, quat)
        for side, i in (('left', 15), ('right', 22)):
            J = kin[side]['jacobian']
            force = 160*(desired_kinematics[side]['position']-kin[side]['position'])-8*(J@dq[i:i+7])
            force *= min(1., 12./max(np.linalg.norm(force),1e-9))
            null = np.eye(7)-J.T@np.linalg.solve(J@J.T+np.eye(3)*.0005,J)
            posture = null@(4*(targets[i:i+7]-q[i:i+7])-.5*dq[i:i+7])
            tau[i:i+7] = kin[side]['gravity'] + J.T@force + posture
            tau[i:i+7] = np.clip(tau[i:i+7], [-20,-20,-20,-20,-20,-4,-4], [20,20,20,20,20,4,4])
            # Update the host spring around the measured arm pose; motion and
            # contact are driven by the bounded Cartesian impedance torque.
            targets[i:i+7] = q[i:i+7]
        command = dict(q=targets, dq=np.zeros(29), kp=self.kp.copy(), kd=self.kd.copy(), tau=tau)
        self.last_command = command
        self.telemetry = dict(state=self.state, age=self.age, right_force=right, front_force=front,
                              force=self.force.copy(), velocity=velocity, command=self.velocity_command.copy(),
                              odometry=self.odometry.position.copy(), hands=np.stack([kin[s]['position'] for s in ('left','right')]),
                              heading=self.heading, yaw=yaw)
        return command
