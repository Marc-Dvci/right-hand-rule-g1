"""Invoked inside the policy image by tools/smoke_image.py."""
import time
start = time.monotonic()
print('Python started',flush=True)
import sys
sys.path.insert(0,'/submission')
import numpy as np
print('NumPy imported',time.monotonic()-start,flush=True)
from policy.controller import Controller
c = Controller()
print('Controller loaded',time.monotonic()-start,flush=True)
q = np.array([0.]*29)
q[15:] = [.2,.2,0,1.28,0,0,0,.2,-.2,0,1.28,0,0,0]
obs = dict(q=q,dq=np.zeros(29),quat=[1,0,0,0],gyro=[0,0,0])
timing = []
for _ in range(100):
    a = time.monotonic()
    result = c.act(obs,ready=False)
    timing.append(time.monotonic()-a)
print('100 calls: median',np.median(timing),'max',max(timing),flush=True)
