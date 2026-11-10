"""Explicit component/vector force errors and timestamp-aligned odometry for the film hero."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]


def main():
    audit=json.loads((ROOT/'reports/v2/primary-audit.json').read_text())
    row=min((r for r in audit['rows'] if r['mode']=='navigate' and r['delay_ms']==0 and r['exited']),key=lambda r:r['seed'])
    path=(ROOT/row['report_path']).parent
    report=json.loads((path/'report.json').read_text())
    with np.load(path/'trace.npz',allow_pickle=False) as z:
        t=z['observation_time'][1:]
        estimate=z['estimated_force'][1:]
        truth=z['true_force_filtered'][:-1]
        odometry=z['odometry'][1:,:2]
        actual=z['qpos'][:-1,:2]-z['qpos'][0,:2]
    selected=t>7
    error=estimate[selected]-truth[selected]
    component=float(np.sqrt(np.mean(error**2)))
    vectors=np.sqrt(np.mean(np.sum(error**2,axis=-1),axis=0))
    vector=float(np.sqrt(np.mean(np.sum(error**2,axis=-1))))
    position_error=np.linalg.norm(odometry-actual,axis=1)
    target=report['controller_parameters']['force_target']
    result=dict(seed=row['seed'],episode=row['report_path'],scope='Disclosed film hero only; not an aggregate estimator guarantee.',
        component_rmse_n=component,mean_hand_vector_rmse_n=vector,per_hand_vector_rmse_n=vectors.tolist(),
        force_target_n=target,mean_hand_vector_rmse_fraction_of_target=vector/target,
        raw_500hz_peak_hand_resultant_n=report['touch_metrics']['peak_500hz_hand_force_n'],
        maximum_odometry_error_m=float(position_error.max()),endpoint_odometry_error_m=float(position_error[-1]),
        alignment='Estimator at observation_time[1:] against the physical interval ending at that observation, true_force_filtered[:-1]; only times >7 s. Odometry is compared with qpos[:-1], not the later end-of-step state.',
        definition='Component RMSE averages squared errors over time, hands and xyz. Vector RMSE first sums xyz squared errors, then averages over time/hands. Per-hand values average over time only. Historical fields named force_vector_rmse_n in the frozen evaluator are component RMSE, not vector-norm RMSE. No metric definition or controller changed during final evaluation.')
    output=ROOT/'reports/v2/hero-metrics.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for n,title,axis,sign in ((0,'Forward probe',0,-1),(1,'Right feeler',1,1)):
        ax=axes[0,n]
        ax.plot(t,sign*truth[:,n,axis],lw=.8,color='#568cd6',label='Contact / matched bandwidth')
        ax.plot(t,sign*estimate[:,n,axis],lw=.8,color='#159b78',label='Joint/IMU estimate')
        ax.set(title=title,xlabel='Simulated seconds',ylabel='Force (N)')
        ax.legend(fontsize=8)
    ax=axes[1,0]
    for wall in report['scene_specification']['walls']:
        points=np.asarray(wall)
        ax.plot(points[:,0],points[:,1],color='#b3bec8',lw=1.5)
    # The initial base XY is effectively zero in the declared scenes; use the
    # recorded origin explicitly when drawing absolute scene coordinates.
    with np.load(path/'trace.npz',allow_pickle=False) as z:
        start=z['qpos'][0,:2]
    ax.plot(*(actual+start).T,color='#568cd6',lw=1,label='Recorded base path')
    ax.plot(*(odometry+start).T,color='#159b78',lw=1,label='Joint/IMU odometry')
    ax.set(aspect='equal',title='Logging-only odometry',xlabel='x (m)',ylabel='y (m)')
    ax.legend(fontsize=8)
    axes[1,1].plot(t,position_error,color='#159b78')
    axes[1,1].set(title='Aligned position error',xlabel='Simulated seconds',ylabel='Error (m)')
    fig.suptitle(f'V2 film hero / seed {row["seed"]} / evaluator truth never enters navigation')
    target_dir=ROOT/'evaluation/results/v2'
    target_dir.mkdir(parents=True,exist_ok=True)
    for extension in ('svg','png','pdf'):
        fig.savefig(target_dir/f'force-and-odometry.{extension}',dpi=160)
    svg=target_dir/'force-and-odometry.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
