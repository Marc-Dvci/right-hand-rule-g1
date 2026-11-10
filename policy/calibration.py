"""Identify command age using a small free-space wrist-roll torque excitation.

Only measured wrist q/dq and locally issued commands enter the regression.
Unknown inertia, damping, gravity slope and Coulomb friction are nuisance fits.
No delay label, simulation clock, base state or contact truth is available.
"""
import numpy as np


class CommandAgeCalibration:
    def __init__(self):
        self.q = []
        self.dq = []
        self.inputs = []
        self.actual = []
        self.scores = None
        self.selected = None
        self.confidence = 0.

    def observe(self, q, dq, *, actual=True):
        self.q.append(float(q))
        self.dq.append(float(dq))
        self.actual.append(bool(actual))

    def issued(self, q_target, tau):
        self.inputs.append(60.*float(q_target)+float(tau))

    @staticmethod
    def excitation(frame):
        # Fixed PRBS, three control frames per bit. No random process or label.
        state=0x5D
        for _ in range((frame//3)%127):
            state=((state<<1)|(((state>>6)^(state>>5))&1))&127
        return .5 if state&1 else -.5

    def fit(self, *, start=0):
        q,dq,u = np.asarray(self.q),np.asarray(self.dq),np.asarray(self.inputs)
        if len(u)!=len(q) or len(q)-start<45:
            raise ValueError('Insufficient calibration coverage')
        indices=np.arange(max(start,2),len(q)-1)
        actual=np.asarray(self.actual,dtype=bool)
        indices=indices[actual[indices]&actual[indices+1]]
        if len(indices)<40 or np.std(u[indices])<.1:
            raise ValueError('Insufficient calibration excitation or real observations')
        qbar=(q[indices]+q[indices+1])/2
        vbar=(dq[indices]+dq[indices+1])/2
        y=(dq[indices+1]-dq[indices])/.02
        scores=[]
        for delay in range(3):
            torque=u[indices-delay]-60*qbar-1.5*vbar
            X=np.column_stack([torque,vbar,qbar,np.sign(vbar),np.ones(len(indices))])
            coefficients=np.linalg.lstsq(X,y,rcond=None)[0]
            residual=np.mean((X@coefficients-y)**2)
            # An inverted or near-zero input response is not a physical inertia.
            if not 1.<coefficients[0]<500.:
                residual+=1e6
            scores.append(float(residual))
        order=np.argsort(scores)
        self.scores=scores
        self.selected=int(order[0])
        self.confidence=float(1-scores[order[0]]/max(scores[order[1]],1e-12))
        if self.confidence<.15 or scores[order[0]]>=1e6:
            self.selected=None
            raise ValueError('Command-age identification is ambiguous')
        return self.selected

    def report(self):
        return dict(selected_frames=self.selected,scores=self.scores,confidence=self.confidence,
            samples=len(self.q),excitation_peak_nm=.5,joint='left_wrist_roll',
            definition='Free-space local input/output regression; 0/20/40 ms hypotheses. No timing label enters the policy.')
