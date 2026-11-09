"""Adapt a reviewed basketball bundle to the team's unchanged scenario runner."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
import re
import time
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np
import policy_safety
import joint_checks
from policy_safety.config import METRICS, profile_config
from policy_safety.evaluation import run_scenario, summarize_scenarios, verdict
from policy_safety.joint_rules import DEFAULT_JOINT_PROFILE, JointRules
from policy_safety.simulation import Simulation
from thrash import ThrashConfig, ThrashDetector

from . import simulation, identify_bundle
from .legacy_tracker import DribbleTracker as LegacyTracker
from .policy import ACTION_SCALE, MLPPolicy

HERE = Path(__file__).parent
MANIFEST = json.loads((HERE / 'bundle.json').read_text())
ADAPTER = MANIFEST['adapter']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_weights(path):
    shapes = {'obs_mean': (115,), 'obs_std': (115,), 'n_layers': ()}
    for i, (a, b) in enumerate([(115, 512), (512, 256), (256, 128), (128, 58)]):
        shapes[f'w{i}'], shapes[f'b{i}'] = (a, b), (b,)
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) != len(shapes) or {i.filename for i in infos} != {k+'.npy' for k in shapes}:
            raise ValueError('Basketball weights must contain the reviewed network tensors.')
        if sum(i.file_size for i in infos) > 4 * 1024 * 1024:
            raise ValueError('Basketball weights exceed the network size limit.')
        for info in infos:
            with archive.open(info) as stream:
                version = np.lib.format.read_magic(stream)
                if version not in ((1, 0), (2, 0)):
                    raise ValueError('Unsupported weight array encoding.')
                read = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, _, dtype = read(stream)
                key = info.filename[:-4]
                if shape != shapes[key] or dtype.hasobject or dtype.kind not in 'fi' or dtype.itemsize > 8:
                    raise ValueError('Basketball weight shape or type does not match the controller.')
    with np.load(path, allow_pickle=False) as arrays:
        if int(arrays['n_layers']) != 4 or any(not np.isfinite(arrays[k]).all() for k in shapes):
            raise ValueError('Basketball weights contain invalid network values.')
        if np.any(arrays['obs_std'] <= 0):
            raise ValueError('Basketball observation normalization must be positive.')


class BasketballAdapter:
    def __init__(self, model, stance, onnx_session=None):
        self.onnx_session = onnx_session
        if onnx_session is None:
            validate_weights(model)
            self.mlp = MLPPolicy(model)
        self.stance = stance
        self.previous_action = np.zeros(29, np.float32)
        self.ball_hist = None
        self.last_raw = np.empty(0)

    def observation(self, obs):
        ball = np.asarray(obs['ball_rel'], np.float32)
        self.ball_hist = np.tile(ball[None], (3, 1)) if self.ball_hist is None else np.concatenate([ball[None], self.ball_hist[:-1]])
        return np.concatenate([np.asarray(obs['gyro'], np.float32), np.asarray(obs['gravity'], np.float32),
            np.asarray(obs['joint_pos_rel'], np.float32), np.asarray(obs['joint_vel'], np.float32),
            self.previous_action, self.ball_hist.ravel(), np.asarray(obs['cue'], np.float32)])[None]

    def infer(self, observation):
        if self.onnx_session is not None:
            from .profile_controller import infer
            self.last_raw = infer(self.onnx_session, observation)
        else:
            self.last_raw = self.mlp.forward(observation[0]).astype(np.float32)
        if self.last_raw.shape != (29,) or not np.isfinite(self.last_raw).all():
            raise ValueError('Invalid basketball inference output.')
        self.previous_action = self.last_raw.copy()
        return self.last_raw

    def decode(self, raw):
        return np.asarray(self.stance, np.float32) + raw * ACTION_SCALE

    def command_velocity_and_torque(self):
        return np.zeros(29), np.zeros(29)

    def snapshot(self):
        return np.concatenate([self.previous_action, np.zeros(18) if self.ball_hist is None else self.ball_hist.ravel()])


class BasketballSimulation(Simulation):
    """Reuse upstream measurements, torque checks, integration and trace recording."""
    def __init__(self, root, seed, stance):
        simulation.HERE = str(root)
        simulation.SCENE = str(root / 'assets/g1_dribble_scene.xml')
        args = SimpleNamespace(timestep=0.002, solver_iterations=0, ball_delay=1, noise=1)
        variant = identify_bundle(root)
        if variant is None:
            raise ValueError("Unrecognized basketball controller assets.")
        tracker = LegacyTracker if variant["tracker"] == "legacy" else simulation.DribbleTracker
        self.source = simulation.Sim(args, tracker_class=tracker)
        self.profile_controller = variant.get('controller') == 'profile-onnx'
        if self.profile_controller:
            from .profile_controller import configure
            configure(self.source, root)
        self.rng = np.random.default_rng(seed)
        self.source.reset(self.rng, stance=stance)
        self.model, self.data = self.source.m, self.source.d
        m = self.model
        self.actuators = np.arange(m.nu)
        ids = m.actuator_trnid[:, 0]
        self.qadr, self.vadr = m.jnt_qposadr[ids], m.jnt_dofadr[ids]
        if m.nu != 29 or not np.array_equal(self.qadr, np.arange(7, 36)) or not np.array_equal(self.vadr, np.arange(6, 35)):
            raise ValueError('Basketball joint mapping changed.')
        self.robot = {'joint_names': [m.joint(int(i)).name for i in ids], 'contract': ADAPTER}
        self.dt, self.physics_dt, self.substeps = 0.02, 0.002, 10
        self.bounds, self.ctrl_bounds = m.jnt_range[ids].copy(), m.actuator_ctrlrange.copy()
        self.torque_bounds = m.actuator_forcerange.copy()
        self.kp, self.kd = m.actuator_gainprm[:, 0].copy(), -m.actuator_biasprm[:, 2].copy()
        self.base = m.body('pelvis').id
        self.state_spec = mujoco.mjtState.mjSTATE_INTEGRATION
        self.command_history = None
        self.thrash_detector = ThrashDetector(ThrashConfig(mode="enforce"), len(self.vadr), max_gap_secs=0.2)

    def observation(self, adapter, command):
        obs, _ = self.source.observe(self.rng)
        return adapter.observation(obs)


def evaluation_context(sim, rules, root):
    """Record actual compiled settings; never substitute the reference profile gains."""
    joints = []
    for i, name, limits in rules.entries:
        joints.append({
            'joint': name, 'kp': float(sim.kp[i]), 'kd': float(sim.kd[i]),
            'model_torque_min_nm': float(sim.torque_bounds[i, 0]),
            'model_torque_max_nm': float(sim.torque_bounds[i, 1]),
            'screening_torque_nm': limits.max_torque_nm,
            'screening_speed_rad_s': limits.max_velocity_rad_secs,
            'reference_kp': limits.kp, 'reference_kd': limits.kd,
        })
    requirements = root / 'requirements-eval.txt'
    declared = None
    if requirements.is_file() and requirements.stat().st_size <= 16384:
        match = re.search(r'^mujoco==([0-9.]+)\s*$', requirements.read_text(errors="replace"), re.M)
        if match:
            declared = match.group(1)
    context = {
        'version': 1, 'simulator': f'MuJoCo {mujoco.__version__} / CPU',
        'submitted_mujoco_version': declared,
        'reference_files': {name: digest(root / name) for name in
                            ('requirements-eval.txt', 'evaluate.py', 'evaluate_mjx.py', 'dribble_env.py')
                            if (root / name).is_file()},
        'gains_source': 'Compiled assets/g1_robot.xml from this upload. No reference-profile gain override or gain randomization.',
        'control_seconds': sim.dt, 'physics_seconds': sim.physics_dt,
        'ball_observation_delay_steps': 1, 'action_delay_steps': 0,
        'observation_noise': 'Enabled: uniform gyro ±0.2 rad/s, gravity ±0.05, joint position ±0.01 rad, joint velocity ±1.5 rad/s, ball position ±0.015 m and ball velocity ±0.15 m/s. Startup joint noise is separate. A no-noise local screen is not the same test.',
        'ball_respawn': False, 'camera_tested': False,
        'startup_note': 'Joint positions start at the authored stance qpos plus uniform ±0.03 rad noise. The initial motor target is the authored stance ctrl. qpos and ctrl are distinct; their difference is not an injected pose offset or a trained-policy action.',
        'limits_note': 'PR #10 shared joint, torque, speed, fall and thrash checks run unchanged. Actual PD demand uses the simulation gains shown here. The profile is provisional; model torque clamps can differ from screening effort limits.',
        'joints': joints,
    }
    if getattr(sim, 'profile_controller', False):
        context.update(
            gains_source='Authored assets/arena_g1_profile.json, matching the submitted safety-mode configuration; no gain randomization. These controller settings do not override the PR #10 checker limits.',
            startup_note='Motor targets are re-solved from the scene stance for the authored profile gains. Joint positions start at those targets plus uniform ±0.005 rad noise. Observations retain the authored stance-position reference.',
            controller_contract='g1-basketball-115-profile-v1',
            controller_execution='Original policy.onnx; graph normalization and controller logic are preserved without a raw-network re-export.')
    return context


def startup_context(sim, rules):
    return [{
        'joint': name, 'stance_position_rad': float(sim.source.stance_qpos[i]),
        'starting_position_rad': float(sim.data.qpos[sim.qadr[i]]),
        'initial_target_rad': float(sim.data.ctrl[i]),
        'target_minus_position_rad': float(sim.data.ctrl[i] - sim.data.qpos[sim.qadr[i]]),
    } for i, name, _ in rules.entries]


def screen(root, output, release, episodes=12, seconds=20.0):
    started = time.monotonic()
    profile_path = Path(policy_safety.__file__).parent / 'profiles/provisional.json'
    profile = profile_config(profile_path)
    if digest(profile_path) != release['profile_sha256'] or digest(DEFAULT_JOINT_PROFILE) != release['joint_profile_sha256']:
        raise ValueError('Installed safety limits do not match the release.')
    expected = next(x for x in release['additional_adapters'] if x['adapter'] == ADAPTER)
    if digest(HERE / 'bundle.json') != expected['robot_config_sha256']:
        raise ValueError('Basketball contract does not match the release.')
    traces = output / 'traces'
    traces.mkdir(parents=True)
    scenarios = []
    context = None
    onnx_session = None
    if identify_bundle(root).get('controller') == 'profile-onnx':
        from .profile_controller import session
        onnx_session = session(root)
    for n in range(episodes):
        seed, stance = 1000 + n, n % 2
        sim = BasketballSimulation(root, seed, stance)
        adapter = BasketballAdapter(root / 'policy_weights.npz', sim.source.stance_ctrl, onnx_session)
        rules = JointRules(sim.robot['joint_names'])
        if context is None:
            context = evaluation_context(sim, rules, root)
        startup = startup_context(sim, rules)
        ball_start = {
            'position_world_m': sim.data.qpos[36:39].tolist(),
            'velocity_world_m_s': sim.data.qvel[35:38].tolist(),
            'pelvis_position_world_m': sim.data.site_xpos[sim.source.sid['imu_in_pelvis']].tolist(),
            'pelvis_quaternion_wxyz': sim.source.sensor('pelvis_quat').tolist(),
            'next_hand': sim.source.tracker.next_hand,
            'released': sim.source.tracker.expect == 1,
        }
        scenario = {'name': f'basketball-{stance}-{seed}', 'kind': 'nominal', 'command': [],
                    'seed': seed, 'stance': stance, 'seconds': seconds, 'upright': True}
        trace = traces / f'{n:05}.npz'
        result, _ = run_scenario(sim, adapter, profile, scenario, trace, joint_rules=rules, continue_after_violation=True)
        result['startup'] = startup
        result['ball_start'] = ball_start
        result['task_metrics'] = {'crossovers': sim.source.tracker.crossings,
                                  'note': 'Observed task behavior only; not a safety verdict or hardware qualification.'}
        scenarios.append(result)
    status, code = verdict(scenarios, profile['calibrated'])
    report = {'version': 1, 'status': status, 'exit_code': code, 'hardware_authorization': False,
        'adapter': ADAPTER, 'controller_variant': identify_bundle(root)['id'], 'self_collisions': identify_bundle(root)['self_collisions'], 'tested_behavior': f'Basketball controller with ball tracking in its fingerprinted task scene. {episodes} independent {seconds:g}-second dribble simulations from both authored stances; same upstream joint, torque, fall, thrash and speed checks. No walker commands, push branches, camera images or physical-robot testing.',
        'profile': profile, 'clip_to_stops': False, 'joint_movement_checks': rules.coverage(),
        'coverage': {'planned': episodes, 'reported': len(scenarios), **{s: sum(x['status'] == s for x in scenarios) for s in ('completed','violation','error','incomplete')}},
        'scenarios': scenarios, 'scenario_summary': summarize_scenarios(scenarios),
        'hashes': {'model': {'policy.onnx': digest(root / 'policy.onnx')} if onnx_session is not None else {'policy_weights.npz': digest(root / 'policy_weights.npz')}, 'profile': digest(profile_path),
                   'joint_profile': digest(DEFAULT_JOINT_PROFILE), 'robot_config': digest(HERE / 'bundle.json'),
                   'robot_assets': {k:v for k,v in identify_bundle(root)['files'].items() if k.startswith('assets/')},
                   'implementation': {p.name:digest(p) for p in HERE.glob('*.py')},
                   'upstream_evaluation': digest(Path(policy_safety.__file__).parent / 'evaluation.py'),
                   'shared_joint_checks': digest(joint_checks.__file__)},
        'versions': {'package': policy_safety.__version__, 'mujoco': mujoco.__version__, 'numpy': np.__version__},
        'acceptance_checks': {'calibrated': False, 'metrics_without_thresholds': sorted(METRICS - set(profile['maxima']) - {'actuator_torque','clipping'}),
             'note': 'Simulation continues after findings to capture motion. Findings do not authorize hardware. Ball state is simulated and delayed; the vision detector is not tested.'}}
    report['evaluation_context'] = context
    report['task_summary'] = {
        'crossovers': sum(x['task_metrics']['crossovers'] for x in scenarios),
        'episodes_with_crossovers': sum(x['task_metrics']['crossovers'] > 0 for x in scenarios),
        'note': 'Zero safety findings does not establish successful ball handling. Camera perception is not tested.',
    }
    context['reference_version'] = identify_bundle(root).get('reference_version', identify_bundle(root)['id'])
    context['solver_iterations'] = int(sim.model.opt.iterations)
    context['line_search_iterations'] = int(sim.model.opt.ls_iterations)
    context['ball_start_contract'] = '/docs/g1-policy-checks#basketball-start'
    if onnx_session is not None:
        report['hashes']['model'] = {'policy.onnx': digest(root / 'policy.onnx')}
    report['wall_seconds'] = time.monotonic() - started
    report['runtime_review'] = {
        'status': 'comparison_required', 'owner': 'HIM',
        'summary': 'The test setup needs review before these findings can be attributed to the policy.',
        'next_step': 'Compare the recorded CPU simulator, observation timing, gains and startup with your submitted run. Reproduce this documented controller contract locally and upload a matching export to rerun automatically. Preserve both reports; do not retune solely to satisfy an unmatched test.',
        'differences': [
            'Arena uses the reviewed CPU bridge, not the submitted MJX or vision evaluator. Equivalence to those reference runs has not been established.',
            'The CPU bridge uses one-step ball observation delay, no action delay and no ball respawn. Submitted MJX behavior can differ in delays, contact tracking, resets and physics.',
            context['gains_source'],
        ],
    }
    (output / 'report.json').write_text(json.dumps(report, allow_nan=False, indent=2)+'\n')
    return report
