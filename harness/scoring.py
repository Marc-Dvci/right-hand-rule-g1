"""Independent geometric scoring; simulator truth is used only here."""
import numpy as np


def score_trajectory(time,qpos,exit_spec,entrance_x=None):
    time = np.asarray(time,dtype=float)
    qpos = np.asarray(qpos,dtype=float)
    if time.ndim!=1 or qpos.ndim!=2 or len(time)!=len(qpos) or qpos.shape[1]<3:
        raise ValueError('Invalid trajectory shapes')
    if not np.isfinite(time).all() or not np.isfinite(qpos).all() or np.any(np.diff(time)<=0):
        raise ValueError('Trajectory must have finite states and increasing timestamps')
    exit_time = None
    axis,line,sign = exit_spec['axis'],exit_spec['value'],exit_spec['sign']
    x = (qpos[:,axis]-line)*sign
    for i in np.flatnonzero((x[:-1]<=0)&(x[1:]>0)):
        alpha = -x[i]/(x[i+1]-x[i])
        y = qpos[i,1]+alpha*(qpos[i+1,1]-qpos[i,1])
        if exit_spec.get('min_y',-np.inf)<y<exit_spec.get('max_y',np.inf):
            exit_time = float(time[i]+alpha*(time[i+1]-time[i]))
            break
    wrong_time = None
    if entrance_x is not None:
        wrong = np.flatnonzero(qpos[:,0]<entrance_x)
        if len(wrong):
            wrong_time = float(time[wrong[0]])
    return dict(exited=exit_time is not None and (wrong_time is None or exit_time<wrong_time),
                exit_time=exit_time,wrong_exit_time=wrong_time)
