"""Run policy through the original HIM checker and log independent task truth."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import json
from pathlib import Path
import sys
import time
import hashlib
import numpy as np
import mujoco

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.kit import Runner
from harness.scenes import make
from policy.controller import Controller


def contact_truth(plant):
    f = np.zeros((2, 3))
    for contact_index, c in enumerate(plant.data.contact):
        for n, side in enumerate(('left', 'right')):
            hand = plant.model.geom(f'{side}_touch_hand').id
            hand_geoms = {hand} | {plant.model.geom(f'{side}_palm{i}').id for i in (1,2,3)}
            if not any(g in hand_geoms for g in c.geom):
                continue
            wrench = np.zeros(6)
            mujoco.mj_contactForce(plant.model, plant.data, contact_index, wrench)
            world = c.frame.reshape(3, 3).T@wrench[:3]
            if c.geom[0] in hand_geoms:
                world = -world
            f[n] += world
    return f


def run(kind, seed, seconds, mode, speed, output, pose='standing'):
    output.mkdir(parents=True, exist_ok=True)
    scene = make(kind, seed)
    spec = json.loads(scene.with_suffix('.json').read_text()) if scene.with_suffix('.json').exists() else {}
    runner = Runner(scene=scene, pose=pose, record_trace=False)
    controller = Controller(mode, speed)
    start = time.monotonic()
    records = {k: [] for k in ('qpos', 'q', 'dq', 'features', 'time', 'command', 'estimated_force', 'true_force', 'velocity', 'odometry', 'state', 'thrash')}
    peak_thrash = 0.
    exited = False
    wrong_exit = False
    previous_position = np.asarray(runner.plant.state()['position'])
    last_print = -20
    from policy.networks import rotation
    while runner.sim_time < seconds and runner.reason is None:
        t = runner.sim_time
        s = runner.feedback(t)
        # This allowlist is the only information crossing the policy boundary.
        obs = {k: s[k] for k in ('q', 'dq', 'quat', 'gyro')}
        frame = controller.act(obs, ready=s['control_ready'])
        frame.update(session_id=runner.session_id, observation_id=s['observation_id'], sequence=runner.commands)
        runner.command({k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in frame.items()}, t)
        runner.step(t)
        telemetry = controller.telemetry
        thrash = runner.thrash_detector.metrics.get('weighted_rms', 0.)
        peak_thrash = max(peak_thrash, thrash)
        truth = contact_truth(runner.plant)@rotation(obs['quat'])
        for k, v in dict(qpos=runner.plant.data.qpos, q=obs['q'], dq=obs['dq'], features=controller.walker.last_features,
                         time=t, command=telemetry['command'], estimated_force=telemetry['force'], true_force=truth,
                         velocity=telemetry['velocity'], odometry=telemetry['odometry'], state=telemetry['state'], thrash=thrash).items():
            records[k].append(np.array(v).copy())
        position = runner.plant.state()['position']
        exit_spec = spec.get('exit')
        if exit_spec:
            axis, line, sign = exit_spec['axis'], exit_spec['value'], exit_spec['sign']
            crossed = (previous_position[axis]-line)*sign <= 0 < (position[axis]-line)*sign
            if crossed:
                exited = exit_spec.get('min_y', -1e9) < position[1] < exit_spec.get('max_y', 1e9)
        if kind == 'maze' and position[0] < -.75:
            wrong_exit = True
        previous_position = np.asarray(position)
        if t-last_print >= 20:
            print(f'{kind} t={t:.1f} state={controller.state} pos={np.round(position, 2)} force R/L={telemetry["right_force"]:.1f}/{telemetry["front_force"]:.1f} odov={np.round(telemetry["velocity"][:2], 2)} cmd={np.round(telemetry["command"], 2)} thrash={peak_thrash:.3f}', flush=True)
            last_print = t
        if exited or wrong_exit:
            break
    report = runner.report()
    report.update(evidence_kind='in_process_unmodified_kit_runner', seed=seed, mode=mode, task=kind,
                  exited=exited, wrong_exit=wrong_exit, thrash_peak=peak_thrash, policy_calls=len(records['time']),
                  final_position=runner.plant.state()['position'], controller_events=controller.events,
                  wall_seconds=time.monotonic()-start, note='ROS container timing not tested by this harness.')
    source_files = sorted((ROOT/'policy').glob('*.py'))+sorted((ROOT/'policy/models').glob('*.json'))+sorted((ROOT/'policy/models').glob('*.npz'))
    source_digest = hashlib.sha256()
    for path in source_files:
        source_digest.update(str(path.relative_to(ROOT)).encode())
        source_digest.update(path.read_bytes())
    report['controller_sha256'] = source_digest.hexdigest()
    report['mujoco_version'] = mujoco.__version__
    report['numpy_version'] = np.__version__
    forces = np.asarray(records['true_force'])
    estimates = np.asarray(records['estimated_force'])
    after_startup = np.asarray(records['time']) > 7
    report['touch_metrics'] = dict(peak_hand_force_n=float(np.linalg.norm(forces,axis=-1).max()),
        force_vector_rmse_n=float(np.sqrt(np.mean((estimates[after_startup]-forces[after_startup])**2))) if after_startup.any() else None)
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    np.savez_compressed(output/'trace.npz', **{k: np.asarray(v) for k, v in records.items()})
    print(json.dumps({k: report[k] for k in ('status','reason','exited','wrong_exit','seconds','thrash_peak','warnings','touch_metrics')}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--scene', choices=('flat', 'wall', 'inner', 'outer', 'maze'), default='wall')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--seconds', type=float, default=90)
    p.add_argument('--mode', default='navigate')
    p.add_argument('--speed', type=float, default=.12)
    p.add_argument('--pose', default='standing')
    p.add_argument('--output', type=Path, default=ROOT/'evidence/development/wall-001')
    args = p.parse_args()
    run(args.scene, args.seed, args.seconds, args.mode, args.speed, args.output, args.pose)
