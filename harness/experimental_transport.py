"""Reconstruct missed 20 ms sensor frames without inventing applied actions."""
import numpy as np


class ExperimentalTimedPolicy:
    def __init__(self,controller,command_delay=.02,waist_kp=190.,waist_kd=3.5,waist_mode='original',prediction_seconds=0.,torque_fraction=1.):
        self.controller = controller
        self.command_delay = command_delay
        self.waist_kp,self.waist_kd = waist_kp,waist_kd
        if waist_mode not in ('original','fixed','limited'):
            raise ValueError('Unknown waist control mode')
        self.waist_mode = waist_mode
        self.waist_target = np.zeros(3)
        self.prediction_seconds = prediction_seconds
        self.torque_fraction = torque_fraction
        walker = getattr(controller,'walker',None)
        if prediction_seconds and walker is not None:
            original_update = walker.update
            def predicted_update(q,dq,quat,gyro,command):
                q = np.asarray(q)+prediction_seconds*np.asarray(dq)
                w,x,y,z = np.asarray(quat,dtype=float)
                a,b,c = np.asarray(gyro)*prediction_seconds/2
                predicted = np.array([w-x*a-y*b-z*c,x+w*a+y*c-z*b,y+w*b-x*c+z*a,z+w*c+x*b-y*a])
                predicted /= np.linalg.norm(predicted)
                return original_update(q,dq,predicted,gyro,command)
            walker.update = predicted_update
        self.previous = None
        self.previous_id = None
        self.reconstructed_frames = 0

    def act(self,observation,observation_id,ready):
        current = {k:np.asarray(observation[k],dtype=float) for k in ('q','dq','quat','gyro')}
        gap = 1 if self.previous_id is None else observation_id-self.previous_id
        if not 1 <= gap <= 5:
            raise ValueError('Observation sequence gap exceeds the 100 ms control envelope')
        held_command = getattr(self.controller,'last_command',None)
        walker = getattr(self.controller,'walker',None)
        held_action = walker.action.copy() if walker is not None else None
        for step in range(1,gap+1):
            if gap==1:
                intermediate = current
            else:
                alpha = step/gap
                intermediate = {k:self.previous[k]+alpha*(current[k]-self.previous[k]) for k in ('q','dq','gyro')}
                old_quat = self.previous['quat']
                new_quat = current['quat']
                if old_quat@new_quat < 0:
                    new_quat = -new_quat
                quat = old_quat+alpha*(new_quat-old_quat)
                intermediate['quat'] = quat/np.linalg.norm(quat)
            result = self.controller.act(intermediate,ready=ready)
            if step<gap:
                # The motor held the last transmitted command during the gap.
                # Estimation and network history must reflect that actual hold.
                if held_command is not None:
                    self.controller.last_command = held_command
                if walker is not None:
                    walker.action = held_action.copy()
        self.reconstructed_frames += gap-1
        if 'tau' in result:
            result = {k:np.asarray(v).copy() for k,v in result.items()}
            # The waist's extra feedback uses a sampled q. A delayed spring
            # introduces approximately K_extra*delay negative damping. Cancel
            # that first-order term before sending it through the host PD loop.
            result['tau'][12:15] = self.waist_kp*(result['q'][12:15]-current['q'][12:15])-(self.waist_kd+self.waist_kp*self.command_delay)*current['dq'][12:15]
            result['tau'][12:15] = np.clip(result['tau'][12:15],[-25,-20,-20],[25,20,20])
            if self.waist_mode!='original':
                desired = np.zeros(3) if self.waist_mode=='fixed' else np.clip(result['q'][12:15],-.15,.15)
                self.waist_target += .2*(desired-self.waist_target)
                result['q'][12:15] = self.waist_target
                result['tau'][12:15] = 0.
                if walker is not None:
                    walker.action[12:15] = np.asarray(self.waist_target/.25,dtype=np.float32)
            if hasattr(self.controller,'last_command'):
                self.controller.last_command = result
            if self.torque_fraction<1 and all(k in result for k in ('q','kp','kd')):
                limits = np.array([88,139,88,139,35,35]*2+[88,35,35]+[25,25,25,25,25,5,5]*2)
                budget = self.torque_fraction*limits
                offset = -result['kd']*current['dq']+result['tau']
                low = current['q']+(-budget-offset)/result['kp']
                high = current['q']+(budget-offset)/result['kp']
                result['q'] = np.clip(result['q'],low,high)
        self.previous = {k:v.copy() for k,v in current.items()}
        self.previous_id = observation_id
        return result
