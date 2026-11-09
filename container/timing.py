"""Reconstruct missed 20 ms sensor frames without inventing applied actions."""
import numpy as np


class TimedPolicy:
    def __init__(self,controller):
        self.controller = controller
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
        self.previous = {k:v.copy() for k,v in current.items()}
        self.previous_id = observation_id
        return result
