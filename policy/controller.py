"""Touch-only wall following over the attributed NVIDIA locomotion policy."""
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from .networks import Walker, rotation
from .kinematics import ArmModel
from .odometry import Odometry
from .settings import load_settings
from .calibration import CommandAgeCalibration


def wrap(a):
    return (a+np.pi) % (2*np.pi)-np.pi


@dataclass(frozen=True)
class Parameters:
    speed: float = .12
    arc_speed: float = .085
    arc_rate: float = .20
    contact_threshold: float = 4.
    lost_threshold: float = 3.
    lost_seconds: float = .6
    turn_rate: float = .24
    front_threshold: float = 5.
    force_target: float = 6.

    def __post_init__(self):
        if any(not np.isfinite(v) or v <= 0 for v in self.__dict__.values()):
            raise ValueError('Controller parameters must be finite and positive')
        if max(self.speed,self.arc_speed) > .35 or max(self.arc_rate,self.turn_rate) > .6:
            raise ValueError('Controller velocity envelope exceeded')


@dataclass(frozen=True)
class ControlParameters:
    waist_kp: float = 190.
    waist_kd: float = 3.5
    waist_gravity: float = 0.
    walker_prediction: float = 0.
    action_filter: float = 1.
    walk_blend: float = 0.
    bounded_navigation: bool = False
    turn_safety: bool = False
    snag_detection: bool = False
    arm_stiffness: float = 20.
    waist_yaw_scale: float = 1.
    force_command_age_steps: int = 0
    robust_touch: bool = False
    stagnation_recovery: bool = False
    measured_turn_heading: bool = False
    calibrate_command_age: bool = False

    def __post_init__(self):
        for key,high in (('waist_kp',190.),('waist_kd',15.),('waist_gravity',1.2),
                         ('walker_prediction',.06),('action_filter',1.),('walk_blend',.1),('waist_yaw_scale',1.)):
            value=getattr(self,key)
            if not np.isfinite(value) or not 0<=value<=high:
                raise ValueError('Invalid control parameter: '+key)
        if self.action_filter<.1:
            raise ValueError('Action filter must retain control authority')
        if any(type(value) is not bool for value in (self.bounded_navigation,self.turn_safety,self.snag_detection,
                self.robust_touch,self.stagnation_recovery,self.measured_turn_heading,self.calibrate_command_age)) or not 8<=self.arm_stiffness<=40:
            raise ValueError('Invalid navigation/compliance control parameter')
        if type(self.force_command_age_steps) is not int or not 0<=self.force_command_age_steps<=2:
            raise ValueError('Force estimation supports 0 to 2 declared command-delay frames')


class Controller:
    """act accepts only q/dq/quat/gyro and host control readiness.

    No maze, contact labels, world coordinates or simulator velocity enter it.
    All distances are estimates from foot kinematics; yaw is from the IMU.
    """
    def __init__(self, mode='navigate', speed=None, parameters=None, control=None):
        if mode not in ('navigate', 'neutral', 'touch_off', 'touch_shuffled', 'walk_test'):
            raise ValueError('Unknown controller mode')
        self.mode = mode
        if parameters is None:
            parameters = load_settings('navigation')
        self.parameters = Parameters(**parameters)
        if control is None:
            control=load_settings('control')
        self.control=ControlParameters(**control)
        self.speed = self.parameters.speed if speed is None else speed
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
        self.command_history = deque(maxlen=3)
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
        self.gyro_average=np.zeros(3)
        self.turn_settle=0.
        self.stagnant=0.
        self.recoveries=0
        self.force_age=np.zeros(2,dtype=int)
        self.force_ambiguity=np.zeros(2)
        self.progress_samples=deque(maxlen=251)
        self.current_yaw=0.
        self.calibration=CommandAgeCalibration()
        self.calibration_actual=True
        self.calibration_start=None
        self.calibration_error=None
        self.identified_command_age=None

    def transition(self, state):
        previous=self.state
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
        self.stagnant=0.
        self.progress_samples.clear()
        if state=='BACKOFF' and self.control.measured_turn_heading:
            self.heading=self.current_yaw
        maneuvers=('BACKOFF','RETRACT_LEFT','RETRACT_RIGHT','TURN','EXTEND')
        if self.control.bounded_navigation or (self.control.turn_safety and (state in maneuvers or previous in maneuvers)):
            self.heading_integral=0.
            self.velocity_integral[:]=0.
            self.turn_settle=0.

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
        self.gyro_average+=.12*(gyro-self.gyro_average)
        R = rotation(quat)
        yaw = np.arctan2(R[1, 0], R[0, 0])
        self.current_yaw=yaw
        kin = self.model.evaluate(q, quat)
        velocity = self.odometry.update(kin['feet'], quat, foot_rotations=kin['foot_rotations'])
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
        calibrating=self.control.calibrate_command_age and self.started and self.age>=3.
        if calibrating and self.identified_command_age is None and self.calibration_error is None:
            self.calibration.observe(q[19],dq[19],actual=self.calibration_actual)
        raw = np.zeros((2, 3))
        if self.last_command is not None:
            applied = self.last_command
            force_age=self.control.force_command_age_steps if self.identified_command_age is None else self.identified_command_age
            self.force_age[:]=force_age
            if force_age and self.command_history:
                applied = self.command_history[-min(len(self.command_history),force_age+1)]
            for n, (side, i) in enumerate((('left', 15), ('right', 22))):
                motor = self.kp[i:i+7]*(applied['q'][i:i+7]-q[i:i+7]) - self.kd[i:i+7]*dq[i:i+7] + applied['tau'][i:i+7]
                residual = kin[side]['gravity'] - motor
                J = kin[side]['jacobian'][:, :4]
                force_world = np.linalg.solve(J@J.T+np.eye(3)*.0002, J@residual[:4])
                raw[n] = R.T @ force_world
                if self.control.robust_touch and self.command_history:
                    hypotheses=[]
                    for previous in reversed(self.command_history):
                        motor=self.kp[i:i+7]*(previous['q'][i:i+7]-q[i:i+7])-self.kd[i:i+7]*dq[i:i+7]+previous['tau'][i:i+7]
                        residual=kin[side]['gravity']-motor
                        hypotheses.append(R.T@np.linalg.solve(J@J.T+np.eye(3)*.0002,J@residual[:4]))
                    hypotheses=np.asarray(hypotheses)
                    # External contact is sparse. Use the least residual among
                    # plausible *past issued* commands, and expose ambiguity.
                    selected=int(np.argmin(np.linalg.norm(hypotheses-self.bias[n],axis=1)))
                    raw[n]=hypotheses[selected]
                    self.force_age[n]=selected
                    self.force_ambiguity[n]=np.linalg.norm(hypotheses-raw[n],axis=1).max()
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
        if self.control.snag_detection:
            # A snag on the right forearm/hand also opposes forward motion.
            front=max(front,-.8*sensed[1,0])
        right = max(0., sensed[1, 1])
        cmd = np.zeros(3)
        travelled = np.linalg.norm((self.odometry.position-self.state_position)[:2])
        if self.state == 'ARMING' and self.age >= 5.:
            if self.control.calibrate_command_age and self.identified_command_age is None:
                try:
                    # The observation just appended has not issued an input yet.
                    # Fit the preceding complete input/output records only.
                    latest=(self.calibration.q.pop(),self.calibration.dq.pop(),self.calibration.actual.pop())
                    self.identified_command_age=self.calibration.fit()
                    self.calibration.observe(latest[0],latest[1],actual=latest[2])
                    self.force[:]=0
                    self.navigation_force[:]=0
                except ValueError as error:
                    self.calibration_error=str(error)
                    self.transition('STOP')
            if self.calibration_error is None:
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
            if self.control.snag_detection and front>self.parameters.front_threshold+1:
                self.transition('BACKOFF')
            elif right > 3.:
                self.transition('FOLLOW')
                self.seek_forward = False
            elif travelled > 1.5 or self.state_age > 25:
                self.transition('STOP')
        elif self.state == 'FOLLOW':
            cmd[0] = self.speed
            cmd[1] = np.clip(.012*(right-self.parameters.force_target), -.07, .07)
            if self.control.stagnation_recovery:
                self.progress_samples.append(self.odometry.position[:2].copy())
                stopped=len(self.progress_samples)==251 and np.linalg.norm(self.progress_samples[-1]-self.progress_samples[0])<.08
                self.stagnant=4. if stopped else 0.
            self.lost = self.lost+.02 if right < self.parameters.lost_threshold else max(0., self.lost-.04)
            if front > self.parameters.front_threshold:
                self.transition('BACKOFF')
            elif self.lost > self.parameters.lost_seconds:
                self.transition('ARC')
            elif self.stagnant>3.:
                self.recoveries+=1
                self.heading=yaw
                self.transition('BACKOFF' if self.recoveries<=8 else 'STOP')
                self.events[-1].update(cause='joint_odometry_stagnation',recovery=self.recoveries)
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
        elif self.state == 'ARC':
            cmd[0] = self.parameters.arc_speed
            self.heading = wrap(self.heading-.19*.02)
            if right > self.parameters.contact_threshold and self.state_age > 1.:
                self.heading = yaw
                self.transition('FOLLOW')
            elif front > self.parameters.front_threshold+1.:
                self.transition('BACKOFF')
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
            if self.control.bounded_navigation or self.control.turn_safety:
                settled=abs(wrap(self.heading-yaw))<.09 and abs(self.gyro_average[2])<.15
                self.turn_settle=self.turn_settle+.02 if settled else 0.
                finished=self.turn_settle>.25
            else:
                finished=abs(wrap(self.heading-yaw))<.075 and abs(gyro[2])<.15
            if finished and self.state_age > 3.:
                self.transition('EXTEND')
            elif self.state_age > 25:
                self.transition('STOP')
        elif self.state == 'EXTEND':
            if self.state_age > 2.:
                self.transition('FIND')
        if self.mode == 'neutral':
            cmd[:] = 0
        if self.state.startswith('RETRACT_') or self.state in ('TURN', 'EXTEND'):
            cmd[:2] = np.clip((R.T@(self.turn_anchor-self.odometry.position))[:2]*.8, -.15, .15)
        if self.state not in ('ARMING', 'STOP') and self.mode != 'neutral':
            err = wrap(self.heading-yaw)
            if not (self.control.bounded_navigation or self.control.turn_safety) or abs(2*err+.5*self.heading_integral)<self.parameters.turn_rate or err*self.heading_integral<0:
                self.heading_integral = np.clip(self.heading_integral+err*.02, -.8, .8)
            cmd[2] = np.clip(2.*err + .5*self.heading_integral, -self.parameters.turn_rate, self.parameters.turn_rate)
            if self.state == 'ARC':
                cmd[2] = -self.parameters.arc_rate
            hold=self.state.startswith('RETRACT_') or self.state in ('TURN','EXTEND')
            if self.control.turn_safety and hold:
                self.velocity_integral[:]=0
                cmd[:2]=np.clip(cmd[:2]+.4*(cmd[:2]-velocity[:2]),-.06,.06)
            elif self.control.bounded_navigation:
                if hold or self.state=='BACKOFF':
                    self.velocity_integral[:]=0
                    limit=.06 if hold else .10
                    cmd[:2]=np.clip(cmd[:2]+.4*(cmd[:2]-velocity[:2]),-limit,limit)
                else:
                    error=np.clip(cmd[:2]-velocity[:2],-.2,.2)
                    candidate=np.clip(self.velocity_integral+error*.02,-.08,.08)
                    raw_cmd=cmd[:2]+.65*error+1.2*candidate
                    limits=np.array([.20,.14])
                    accept=(abs(raw_cmd)<limits)|(error*self.velocity_integral<0)
                    self.velocity_integral=np.where(accept,candidate,self.velocity_integral)
                    cmd[:2]=np.clip(cmd[:2]+.65*error+1.2*self.velocity_integral,[-.12,-.14],limits)
            else:
                self.velocity_integral += (cmd[:2]-velocity[:2])*.02
                self.velocity_integral = np.clip(self.velocity_integral, -.25, .25)
                cmd[:2] = np.clip(cmd[:2]+.9*(cmd[:2]-velocity[:2])+1.8*self.velocity_integral, [-.25,-.3], [.4,.3])
        if max(front, right) > 35 and self.state not in ('RETRACT_LEFT', 'RETRACT_RIGHT', 'TURN', 'EXTEND', 'BACKOFF'):
            self.transition('GUARD')
        if self.state in ('ARMING', 'STOP', 'GUARD') or self.mode == 'neutral':
            cmd[:] = 0
            self.velocity_integral *= .95
        braking=self.control.turn_safety and (self.state=='BACKOFF' or self.state.startswith('RETRACT_'))
        slew=.009 if braking else .003
        self.velocity_command += np.clip(cmd-self.velocity_command, [-slew,-slew,-.006], [slew,slew,.006])
        prediction=self.control.walker_prediction
        future_q=q+prediction*dq
        w,x,y,z=quat
        a,b,c=gyro*prediction/2
        future_quat=np.array([w-x*a-y*b-z*c,x+w*a+y*c-z*b,y+w*b-x*c+z*a,z+w*c+x*b-y*a])
        future_quat/=np.linalg.norm(future_quat)
        lower = self.walker.update(future_q,dq,future_quat,gyro,self.velocity_command,
                                  action_filter=self.control.action_filter,blend_width=self.control.walk_blend)
        if self.control.waist_yaw_scale!=1.:
            lower[12]*=self.control.waist_yaw_scale
            # The next history frame must describe the target actually sent.
            self.walker.action[12]=lower[12]/.25
        target_alpha = 0. if self.state.startswith('RETRACT_') or self.state in ('TURN', 'GUARD', 'STOP') else min(1., self.age/3.)
        self.arm_alpha += np.clip(target_alpha-self.arm_alpha, -.012, .012)
        targets = np.r_[lower, self.initial_arms+self.arm_alpha*(self.arm_pose-self.initial_arms)]
        if self.state in ('FOLLOW', 'FIND', 'CLEAR') and self.mode not in ('neutral', 'touch_off'):
            J = R.T @ kin['right']['jacobian'][:, :4]
            dy = np.clip(.012*(right-self.parameters.force_target)-velocity[1], -.16, .16)*.02
            step = J.T@np.linalg.solve(J@J.T+np.eye(3)*.001, [0, dy, 0])
            self.right_adjustment[:4] = np.clip(self.right_adjustment[:4]+step, -.35, .35)
        else:
            self.right_adjustment *= .96
        targets[22:] += self.arm_alpha*self.right_adjustment
        tau = np.zeros(29)
        tau[12:15] = np.clip(self.control.waist_kp*(targets[12:15]-q[12:15])-
            self.control.waist_kd*dq[12:15]+self.control.waist_gravity*kin['waist_gravity'],
            [-25,-20,-20],[25,20,20])
        tau[12]*=self.control.waist_yaw_scale
        for side, i in (('left', 15), ('right', 22)):
            tau[i:i+7] = kin[side]['gravity']*self.arm_alpha
            tau[i:i+7] -= (60-self.control.arm_stiffness)*self.arm_alpha*(targets[i:i+7]-q[i:i+7])
            tau[i:i+7] = np.clip(tau[i:i+7], [-20,-20,-20,-20,-20,-4,-4], [20,20,20,20,20,4,4])
        if self.control.calibrate_command_age and 3.2<=self.age<4.8:
            tau[19]+=self.calibration.excitation(int(round((self.age-3.2)/.02)))
        command = dict(q=targets, dq=np.zeros(29), kp=self.kp.copy(), kd=self.kd.copy(), tau=tau)
        self.last_command = command
        self.command_history.append({k:command[k].copy() for k in ('q','tau')})
        if calibrating and len(self.calibration.inputs)<len(self.calibration.q):
            self.calibration.issued(targets[19],tau[19])
        self.telemetry = dict(state=self.state, age=self.age, right_force=right, front_force=front,
                              force=self.force.copy(), velocity=velocity, command=self.velocity_command.copy(),
                              odometry=self.odometry.position.copy(), hands=np.stack([kin[s]['position'] for s in ('left','right')]),
                              heading=self.heading, yaw=yaw)
        self.telemetry.update(force_command_age=self.force_age.copy(),force_ambiguity_n=self.force_ambiguity.copy(),
                              recoveries=self.recoveries)
        return command
