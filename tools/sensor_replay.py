"""Export/replay a sensor-only command proof. Replay needs Python and NumPy only."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.controller import Controller
from container.timing import TimedPolicy


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            value.update(chunk)
    return value.hexdigest()


def policy_digest():
    value=hashlib.sha256()
    files=sorted((ROOT/'policy').glob('*.py'))+sorted((ROOT/'policy/models').glob('*.json'))+sorted((ROOT/'policy/models').glob('*.npz'))
    for path in files:
        value.update(path.relative_to(ROOT).as_posix().encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def export(episode,output):
    if output.exists():
        raise ValueError('Refusing to replace an existing sensor proof')
    report=json.loads((episode/'report.json').read_text())
    if report['controller_sha256']!=policy_digest():
        raise ValueError('Episode and current policy source differ')
    handoff=report['policy_handoff_at_secs']
    if handoff is None:
        raise ValueError('No policy handoff to replay')
    with np.load(episode/'trace.npz',allow_pickle=False) as trace:
        meta=dict(controller_sha256=report['controller_sha256'],parameters=report['controller_parameters'],
            control=report['control_parameters'],mode=report['mode'],transport=report['transport_adapter'],
            deployment=report['transport_config'] or {'max_gap_frames':5},
            original_report_sha256=digest(episode/'report.json'),original_trace_sha256=digest(episode/'trace.npz'),
            readiness='Recorded host_ready channel' if 'host_ready' in trace else 'Canonical runner handoff takes effect after the step at handoff time; observation_time > handoff',
            definition='Only q/dq, IMU quaternion/gyro, host readiness and observation ID enter the replayed policy. '
                       'Expected issued commands are compared after each inference; they never enter the controller. '
                       'No maze, simulator base state, contacts, physics engine or episode seed is in this bundle.')
        count=len(trace['q'])
        output.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(output,metadata=json.dumps(meta),q=trace['q'],dq=trace['dq'],
            quat=trace['observation_quat'],gyro=trace['observation_gyro'],
            ready=trace['host_ready'] if 'host_ready' in trace else trace['observation_time']>handoff,observation_id=np.arange(1,count+1),
            expected_targets=trace['issued_targets'],expected_feedforward=trace['issued_feedforward'])


def replay(bundle,output=None,tolerance=0.):
    if not np.isfinite(tolerance) or tolerance<0:
        raise ValueError('Replay tolerance must be finite and nonnegative')
    with np.load(bundle,allow_pickle=False) as archive:
        allowed={'metadata','q','dq','quat','gyro','ready','observation_id','expected_targets','expected_feedforward'}
        if set(archive.files)!=allowed:
            raise ValueError('Bundle contains unexpected/privileged channels')
        data={key:archive[key] for key in allowed if key!='metadata'}
        meta=json.loads(str(archive['metadata']))
    if meta['controller_sha256']!=policy_digest():
        raise ValueError('Sensor proof is from another source version')
    controller=Controller(meta['mode'],parameters=meta['parameters'],control=meta['control'])
    timing=TimedPolicy(controller,**meta['deployment']) if meta['transport'] else None
    worst=0.
    count=len(data['q'])
    for i in range(count):
        obs={key:data[key][i] for key in ('q','dq','quat','gyro')}
        command=timing.act(obs,int(data['observation_id'][i]),bool(data['ready'][i])) if timing else controller.act(obs,ready=bool(data['ready'][i]))
        worst=max(worst,float(np.max(abs(command['q']-data['expected_targets'][i]))),
                        float(np.max(abs(command['tau']-data['expected_feedforward'][i]))))
        if worst>tolerance:
            raise ValueError(f'Command replay mismatch at frame {i}: {worst}')
    result=dict(policy_calls=count,source_matches=True,maximum_absolute_command_difference=worst,
        bitwise_numeric_match=worst==0.,tolerance=tolerance,bundle_sha256=digest(bundle),
        simulator_imported=any(name=='mujoco' or name.startswith('mujoco.') for name in sys.modules),
        inputs=['q','dq','quat','gyro','host_ready','observation_id'],
        numpy_version=np.__version__,controller_sha256=meta['controller_sha256'])
    if output:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--export',type=Path,help='Episode directory; creates the sensor-only bundle')
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--tolerance',type=float,default=0.)
    args=parser.parse_args()
    if args.export:
        export(args.export,args.bundle)
    print(json.dumps(replay(args.bundle,args.output,args.tolerance),indent=2))
