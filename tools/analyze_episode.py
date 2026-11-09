"""Publish force, odometry and contact-map errors using evaluator truth only."""
import os
os.environ['MPLBACKEND']='Agg'
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.kinematics import ArmModel

p=argparse.ArgumentParser()
p.add_argument('episode',type=Path)
p.add_argument('--output',type=Path,default=ROOT/'reports/hero')
a=p.parse_args()
r=json.loads((a.episode/'report.json').read_text())
with np.load(a.episode/'trace.npz',allow_pickle=False) as z:
    t=z['observation_time']
    estimates=z['estimated_force'][1:]
    truth=z['true_force_filtered'][:-1]
    after=t[1:]>7
    rmse=float(np.sqrt(np.mean((estimates[after]-truth[after])**2)))
    true_position=z['qpos'][:,:2]-z['qpos'][0,:2]
    odo=z['odometry'][:,:2]
    error=np.linalg.norm(odo-true_position,axis=1)
    kin=ArmModel()
    actual_contacts=[]
    inferred_contacts=[]
    for i in range(0,len(t),5):
        if np.linalg.norm(z['true_force'][i,1])>3:
            hand=kin.evaluate(z['q'][i],z['qpos'][i,3:7])['right']['position'][:2]
            actual_contacts.append(z['qpos'][i,:2]+hand)
            inferred_contacts.append(z['qpos'][0,:2]+odo[i]+hand)
    actual=np.asarray(actual_contacts)
    inferred=np.asarray(inferred_contacts)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for side,n in (('Forward probe',0),('Right feeler',1)):
        axis=axes[0,n]
        component,sign=(0,-1) if n==0 else (1,1)
        axis.plot(t[1:],sign*truth[:,n,component],color='#568cd6',lw=.8,label='Contact, matched bandwidth')
        axis.plot(t[1:],sign*estimates[:,n,component],color='#129d77',lw=.8,label='Joint/IMU estimate')
        axis.set(title=side,xlabel='Simulated seconds',ylabel='Force (N)')
        axis.legend(fontsize=8)
    axis=axes[1,0]
    for wall in r['scene_specification']['walls']:
        points=np.asarray(wall)
        axis.plot(points[:,0],points[:,1],color='#a2aeb7',lw=2)
    axis.scatter(actual[:,0],actual[:,1],s=2,color='#568cd6',label='Contact truth')
    axis.scatter(inferred[:,0],inferred[:,1],s=2,color='#129d77',label='Kinematic touch map')
    axis.set(aspect='equal',xlabel='x (m)',ylabel='y (m)',title='Logging-only touch map')
    axis.legend(fontsize=8)
    axes[1,1].plot(t,error,color='#129d77')
    axes[1,1].set(xlabel='Simulated seconds',ylabel='Position error (m)',title='Stance-foot odometry vs base truth')
    a.output.mkdir(parents=True,exist_ok=True)
    for extension in ('png','svg','pdf'):
        fig.savefig(a.output/f'force-and-touch-map.{extension}',dpi=180)
    plt.close(fig)
    results=dict(seed=r['seed'],bandwidth_matched_force_vector_rmse_n=rmse,
        force_target_n=r['controller_parameters']['force_target'],
        relative_force_rmse=rmse/r['controller_parameters']['force_target'],
        maximum_odometry_error_m=float(error.max()),endpoint_odometry_error_m=float(error[-1]),
        median_contact_map_error_m=float(np.median(np.linalg.norm(actual-inferred,axis=1))),
        raw_500hz_peak_hand_force_n=r['touch_metrics']['peak_500hz_hand_force_n'],
        note='Map is logging-only. Contact samples selected with simulation truth for evaluation, never navigation. Force alignment is causal and bandwidth-matched; raw peaks are not filtered away.')
    (a.output/'metrics.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
