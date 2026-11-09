"""Gate 0: exercise locomotion in HIM's unmodified Runner, not a ROS container."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.kit import Runner
from policy.networks import Walker
from policy.networks import rotation


def run(seconds, speed, output, arms=True):
    output.mkdir(parents=True, exist_ok=True)
    runner = Runner(record_trace=False)
    walker = Walker()
    profile = runner.rules.entries
    kp = np.array([lim.kp for _, _, lim in profile])
    kd = np.array([lim.kd for _, _, lim in profile])
    arm_target = np.array([-1.0, .15, 0, .4, 0, 0, 0, 0, -.9, 0, .8, 0, 0, 0]) if arms else np.zeros(14)
    states, features, command_log = [], [], []
    peak_thrash = 0.
    start = time.monotonic()
    last_print = -10
    smoothed = np.zeros(3)
    desired_yaw = None
    heading_integral = 0.
    initial_arms = runner.plant.q()[15:].copy()
    while runner.sim_time < seconds and runner.reason is None:
        t = runner.sim_time
        s = runner.feedback(t)
        handoff = s['policy_handoff_at_secs']
        elapsed = 0 if handoff is None else max(0., t - handoff - 2.)
        cmd = np.zeros(3)
        if 2 < elapsed < 30:
            cmd[0] = speed
        elif 31 < elapsed < 37:
            cmd[2] = .3
        elif 38 < elapsed < 44:
            cmd[2] = -.3
        elif 45 < elapsed < 51:
            cmd[1] = -.1
        yaw = float(np.arctan2(rotation(s['quat'])[1, 0], rotation(s['quat'])[0, 0]))
        if desired_yaw is None or handoff is None:
            desired_yaw = yaw
        desired_yaw += cmd[2] * .02
        error = (desired_yaw-yaw+np.pi) % (2*np.pi)-np.pi
        heading_integral = np.clip(heading_integral + error*.02, -1., 1.)
        cmd[2] = np.clip(cmd[2] + 3.*error + .6*heading_integral, -.6, .6)
        smoothed += np.clip(cmd-smoothed, [-.004, -.003, -.008], [.004, .003, .008])
        target = np.asarray(s['q']).copy()
        target[:15] = walker.update(s['q'], s['dq'], s['quat'], s['gyro'], smoothed)
        alpha = min(1., elapsed / 2.)
        alpha = alpha * alpha * (3-2*alpha)
        target[15:] = initial_arms + alpha * (arm_target-initial_arms)
        frame = dict(q=target, dq=np.zeros(29), kp=kp, kd=kd, tau=np.zeros(29),
                     session_id=runner.session_id, observation_id=s['observation_id'], sequence=runner.commands)
        runner.command({k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in frame.items()}, t)
        runner.step(t)
        peak_thrash = max(peak_thrash, runner.thrash_detector.metrics.get('weighted_rms', 0.))
        states.append(runner.plant.data.qpos.copy())
        features.append(walker.last_features.copy())
        command_log.append(smoothed.copy())
        if t-last_print >= 10:
            print(f't={t:.1f} handoff={handoff} position={np.round(runner.plant.state()["position"], 3)} thrash_peak={peak_thrash:.3f}', flush=True)
            last_print = t
    report = runner.report()
    report.update(evidence_kind='in_process_unmodified_kit_runner', thrash_peak=peak_thrash,
                  speed=speed, wall_seconds=time.monotonic()-start,
                  note='Not a submitted-container test; ROS timing and ARM64 remain separate.')
    (output / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    np.savez_compressed(output / 'trace.npz', qpos=np.array(states), features=np.array(features), commands=np.array(command_log), dt=.02)
    print(json.dumps({k: report[k] for k in ('status', 'reason', 'seconds', 'thrash_peak', 'wall_seconds', 'warnings')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--speed', type=float, default=.25)
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/walker/dev-001')
    parser.add_argument('--no-arms', action='store_true')
    args = parser.parse_args()
    run(args.seconds, args.speed, args.output, not args.no_arms)
